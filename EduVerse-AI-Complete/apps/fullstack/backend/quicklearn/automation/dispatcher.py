"""Event dispatcher for Autonomous Workflows.

Bridges business events to background PostgreSQL jobs with idempotency keys,
priority mapping, and rule checking.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from ..db.enums import JobType
from ..db.session import session_scope
from ..jobs import queue as jq
from .rules import is_rule_enabled

log = logging.getLogger(__name__)

EVENT_RULE_MAPPING: dict[str, tuple[str, JobType, int]] = {
    # event_name: (rule_name, job_type, default_priority)
    "syllabus_uploaded": ("auto_syllabus_extraction", JobType.AUTONOMOUS_SYLLABUS, 85),
    "course_material_uploaded": ("auto_material_mapping", JobType.AUTONOMOUS_MATERIAL, 75),
    "previous_paper_uploaded": ("auto_paper_analysis", JobType.AUTONOMOUS_PAPER, 80),
    "exam_session_completed": ("auto_exam_evaluation", JobType.AUTONOMOUS_EXAM_EVAL, 90),
    "scheduled_revision_due": ("daily_revision_scheduler", JobType.AUTONOMOUS_REVISION, 60),
    "exam_date_added": ("exam_readiness_monitor", JobType.AUTONOMOUS_READINESS, 50),
    "weekly_report_due": ("weekly_intelligence_report", JobType.AUTONOMOUS_WEEKLY, 40),
    "audit_check_due": ("evidence_audit_engine", JobType.AUTONOMOUS_AUDIT, 45),
}


def trigger_event(
    event_name: str,
    payload: dict[str, Any],
    user_id: int | None = None,
    source_id: int | None = None,
    idempotency_key: str | None = None,
) -> int | None:
    """Trigger an academic event. If enabled by automation rules, enqueues background job."""
    mapping = EVENT_RULE_MAPPING.get(event_name)
    if not mapping:
        log.warning("Unknown automation event: %s", event_name)
        return None

    rule_name, job_type, priority = mapping

    with session_scope() as session:
        enabled = is_rule_enabled(session, rule_name, user_id=user_id)

    if not enabled:
        log.info("Automation rule '%s' is disabled. Skipping event '%s'.", rule_name, event_name)
        return None

    # Derive sensible idempotency key if none passed
    if not idempotency_key:
        if event_name == "syllabus_uploaded":
            idempotency_key = f"syllabus_{payload.get('course_id')}_{payload.get('source_id')}"
        elif event_name == "course_material_uploaded":
            idempotency_key = f"material_{payload.get('course_id')}_{payload.get('source_id')}"
        elif event_name == "previous_paper_uploaded":
            idempotency_key = f"paper_{payload.get('course_id')}_{payload.get('paper_id')}"
        elif event_name == "exam_session_completed":
            idempotency_key = f"exam_eval_{payload.get('session_id')}"
        elif event_name == "scheduled_revision_due":
            today_str = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
            idempotency_key = f"daily_rev_{user_id}_{today_str}"
        elif event_name == "weekly_report_due":
            week_str = dt.datetime.now(dt.timezone.utc).strftime("%Y-W%W")
            idempotency_key = f"weekly_{user_id}_{week_str}"
        elif event_name == "exam_date_added":
            idempotency_key = f"readiness_{payload.get('course_id')}_{dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d')}"
        elif event_name == "audit_check_due":
            idempotency_key = f"audit_{payload.get('course_id')}_{dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d')}"

    actual_source_id = source_id or payload.get("source_id")

    job_id = jq.enqueue(
        job_type,
        payload=payload,
        source_id=actual_source_id,
        user_id=user_id,
        priority=priority,
        idempotency_key=idempotency_key,
        max_attempts=3,
    )
    log.info("Dispatched event '%s' -> Job %s (type=%s, priority=%s)", event_name, job_id, job_type, priority)
    return job_id
