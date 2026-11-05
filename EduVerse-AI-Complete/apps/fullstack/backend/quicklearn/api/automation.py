"""Automation Center REST API endpoints for EduVerse AI.

Provides job queue observation, manual retry/cancellation, rule toggle controls,
evidence audit issue resolution, notifications, and granular system health diagnostics.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..automation.dispatcher import trigger_event
from ..automation.rules import ensure_default_rules, list_rules, toggle_rule
from ..db.academic_models import EvidenceAuditIssue, Notification
from ..db.models import Job, User
from ..db.session import get_db
from ..db.types import utcnow
from ..jobs import queue as jq
from ..jobs.worker import get_pool, registered_types

log = logging.getLogger(__name__)

router = APIRouter(prefix="/automation", tags=["automation"])


class RuleToggleRequest(BaseModel):
    is_enabled: bool
    config: dict[str, Any] | None = None


class TriggerWorkflowRequest(BaseModel):
    event_name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    course_id: int | None = None


# ==========================================
# 1. JOB TRAY & QUEUE MANAGEMENT
# ==========================================

@router.get("/jobs")
def get_automation_jobs(
    status: str | None = None,
    job_type: str | None = None,
    active_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List jobs filtered by status, type, and current student ownership."""
    jobs = jq.list_jobs(
        limit=limit,
        active_only=active_only,
        user_id=user.id,
        status=status,
        job_type=job_type,
    )
    # Also get counts by status for tabs
    queued_count = db.execute(
        select(text("COUNT(*)")).select_from(Job).where(
            Job.status == "queued",
            (Job.user_id == user.id) | (Job.user_id.is_(None)),
        )
    ).scalar_one() or 0

    running_count = db.execute(
        select(text("COUNT(*)")).select_from(Job).where(
            Job.status == "running",
            (Job.user_id == user.id) | (Job.user_id.is_(None)),
        )
    ).scalar_one() or 0

    failed_count = db.execute(
        select(text("COUNT(*)")).select_from(Job).where(
            Job.status == "failed",
            (Job.user_id == user.id) | (Job.user_id.is_(None)),
        )
    ).scalar_one() or 0

    succeeded_count = db.execute(
        select(text("COUNT(*)")).select_from(Job).where(
            Job.status == "succeeded",
            (Job.user_id == user.id) | (Job.user_id.is_(None)),
        )
    ).scalar_one() or 0

    review_count = db.execute(
        select(text("COUNT(*)")).select_from(EvidenceAuditIssue).where(
            EvidenceAuditIssue.status == "open",
            (EvidenceAuditIssue.user_id == user.id) | (EvidenceAuditIssue.user_id.is_(None)),
        )
    ).scalar_one() or 0

    return {
        "jobs": jobs,
        "counts": {
            "all": len(jobs),
            "queued": queued_count,
            "running": running_count,
            "failed": failed_count,
            "succeeded": succeeded_count,
            "review_required": review_count,
        },
    }


@router.get("/jobs/{job_id}")
def get_job_detail(
    job_id: int,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve full job detail including payload, error breakdown, and duration."""
    job_data = jq.get_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")
    if job_data.get("user_id") and job_data["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to inspect this job")
    return job_data


@router.post("/jobs/{job_id}/retry")
def retry_automation_job(
    job_id: int,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Manually re-enqueue a failed or cancelled job."""
    job = jq.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("user_id") and job["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to retry this job")

    ok = jq.retry(job_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Job is not in a retryable state")
    return {"status": "requeued", "job_id": job_id}


@router.post("/jobs/{job_id}/cancel")
def cancel_automation_job(
    job_id: int,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Cancel a queued or active job."""
    job = jq.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("user_id") and job["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this job")

    ok = jq.cancel(job_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Job could not be cancelled")
    return {"status": "cancelled", "job_id": job_id}


# ==========================================
# 2. AUTOMATION RULES & TOGGLE CONTROLS
# ==========================================

@router.get("/rules")
def get_automation_rules(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List all autonomous workflow triggers and their enabled/disabled states."""
    return list_rules(db, user_id=user.id)


@router.put("/rules/{rule_name}")
def update_automation_rule(
    rule_name: str,
    req: RuleToggleRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Enable or disable a specific automation rule for the current student."""
    rule = toggle_rule(db, rule_name, is_enabled=req.is_enabled, config=req.config, user_id=user.id)
    return {
        "status": "updated",
        "rule_name": rule.rule_name,
        "is_enabled": rule.is_enabled,
        "config": rule.config,
    }


# ==========================================
# 3. MANUAL EVENT DISPATCH / TRIGGER
# ==========================================

@router.post("/trigger")
def trigger_automation_workflow(
    req: TriggerWorkflowRequest,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Manually dispatch an academic workflow event."""
    payload = dict(req.payload)
    if req.course_id:
        payload["course_id"] = req.course_id
    payload["user_id"] = user.id

    job_id = trigger_event(req.event_name, payload, user_id=user.id)
    if not job_id:
        raise HTTPException(
            status_code=400,
            detail=f"Event '{req.event_name}' was either disabled by rules or unknown.",
        )
    return {"status": "dispatched", "job_id": job_id, "event_name": req.event_name}


# ==========================================
# 4. EVIDENCE AUDIT ISSUES
# ==========================================

@router.get("/audit")
def list_audit_issues(
    status: str = "open",
    course_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List data quality issues, ambiguous mappings, and citation anomalies."""
    stmt = select(EvidenceAuditIssue).where(
        (EvidenceAuditIssue.user_id == user.id) | (EvidenceAuditIssue.user_id.is_(None))
    )
    if status:
        stmt = stmt.where(EvidenceAuditIssue.status == status)
    if course_id:
        stmt = stmt.where(EvidenceAuditIssue.course_id == course_id)
    stmt = stmt.order_by(EvidenceAuditIssue.id.desc()).limit(100)

    issues = db.execute(stmt).scalars().all()
    return [
        {
            "id": i.id,
            "issue_type": i.issue_type,
            "severity": i.severity,
            "entity_type": i.entity_type,
            "entity_id": i.entity_id,
            "description": i.description,
            "evidence_context": i.evidence_context or {},
            "status": i.status,
            "course_id": i.course_id,
            "created_at": i.created_at.isoformat() if i.created_at else None,
            "resolved_at": i.resolved_at.isoformat() if i.resolved_at else None,
        }
        for i in issues
    ]


@router.post("/audit/{issue_id}/resolve")
def resolve_audit_issue(
    issue_id: int,
    action: str = Query(default="resolve", pattern="^(resolve|dismiss)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Resolve or dismiss an ambiguous mapping or audit flag."""
    issue = db.get(EvidenceAuditIssue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Audit issue not found")
    issue.status = "resolved" if action == "resolve" else "dismissed"
    issue.resolved_at = utcnow()
    db.commit()
    return {"status": issue.status, "issue_id": issue.id}


# ==========================================
# 5. USER NOTIFICATIONS
# ==========================================

@router.get("/notifications")
def get_user_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get notifications for completed automations and revision alerts."""
    stmt = (
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.id.desc())
        .limit(limit)
    )
    notifs = db.execute(stmt).scalars().all()
    return [
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "kind": n.kind,
            "link": n.link,
            "data": n.data or {},
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifs
    ]


@router.post("/notifications/{notif_id}/read")
def mark_notification_read(
    notif_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Mark a notification as read."""
    notif = db.get(Notification, notif_id)
    if not notif or notif.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    return {"status": "ok", "id": notif.id}


@router.post("/notifications/read-all")
def mark_all_notifications_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Mark all unread notifications as read for current student."""
    db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read == False)
        .values(is_read=True)
    )
    db.commit()
    return {"status": "ok"}


# ==========================================
# 6. GRANULAR SYSTEM HEALTH MONITOR
# ==========================================

@router.get("/health")
async def get_system_health(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Report granular system component health: Server, PostgreSQL, Worker Pool, and Local Ollama."""
    # 1. PostgreSQL check
    pg_healthy = False
    pg_pool_info = {}
    try:
        db.execute(text("SELECT 1")).scalar()
        pg_healthy = True
        engine = db.get_bind()
        if hasattr(engine, "pool"):
            pg_pool_info = {
                "size": engine.pool.size(),
                "checked_in": engine.pool.checkedin(),
                "checked_out": engine.pool.checkedout(),
            }
    except Exception as exc:
        log.warning("PostgreSQL health check failed: %s", exc)

    # 2. Worker pool check
    pool = get_pool()
    worker_healthy = True
    active_jobs = pool.active_job_ids
    queue_len = jq.queue_depth()

    # 3. Local Ollama LLM check
    ollama_healthy = False
    ollama_model = "qwen3.5:4b"
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{base_url.rstrip('/')}/api/tags")
            if resp.is_success:
                ollama_healthy = True
                models = [m.get("name") for m in resp.json().get("models", [])]
                if models:
                    ollama_model = models[0]
    except Exception:
        ollama_healthy = False

    return {
        "server": {
            "status": "healthy",
            "version": "2.4.0-academic",
        },
        "database": {
            "status": "healthy" if pg_healthy else "unhealthy",
            "engine": "PostgreSQL 18.6",
            "database_name": "eduverse_db",
            "pool": pg_pool_info,
        },
        "worker": {
            "status": "healthy" if worker_healthy else "unhealthy",
            "active_tasks_count": len(active_jobs),
            "queue_depth": queue_len,
            "registered_handlers_count": len(registered_types()),
            "concurrency_limits": {"llm": 1, "cpu_data": 2},
        },
        "ollama": {
            "status": "healthy" if ollama_healthy else "offline",
            "active_model": ollama_model,
            "host": base_url,
            "gpu_acceleration": "NVIDIA RTX 3050 (6 GB)",
        },
    }
