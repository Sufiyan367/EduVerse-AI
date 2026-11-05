"""PostgreSQL and SQLite-backed durable job queue for autonomous and pipeline workflows.

Uses PostgreSQL transactions with SELECT ... FOR UPDATE SKIP LOCKED, lease heartbeats,
priority queueing, idempotency keys, exponential backoff retries, and multi-tenant isolation.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, text, update

from ..db.enums import JobStatus, JobType
from ..db.models import Job
from ..db.session import session_scope
from ..db.types import utcnow
from .events import emit

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
DEFAULT_LEASE_SECONDS = 120


@dataclass(slots=True)
class ClaimedJob:
    """Detached snapshot of a claimed job."""

    id: int
    type: JobType
    payload: dict[str, Any]
    source_id: int | None
    parent_id: int | None
    attempts: int
    user_id: int | None = None
    priority: int = 50
    max_attempts: int = MAX_ATTEMPTS


def enqueue(
    job_type: JobType,
    *,
    payload: dict[str, Any] | None = None,
    source_id: int | None = None,
    parent_id: int | None = None,
    dedupe_key: str = "",
    user_id: int | None = None,
    priority: int = 50,
    idempotency_key: str | None = None,
    next_run_at: dt.datetime | None = None,
    max_attempts: int = MAX_ATTEMPTS,
) -> int:
    """Add a job, or revive/reuse the matching idempotent one."""
    payload = payload or {}
    now = utcnow()
    with session_scope() as session:
        existing: Job | None = None

        # 1. Idempotency check via idempotency_key
        if idempotency_key:
            existing = session.execute(
                select(Job).where(Job.idempotency_key == idempotency_key)
            ).scalar_one_or_none()
            if existing is not None:
                if existing.status in {JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.SUCCEEDED}:
                    return existing.id

        # 2. Existing check via (source_id, type, dedupe_key)
        if existing is None and source_id is not None:
            existing = session.execute(
                select(Job).where(
                    Job.source_id == source_id,
                    Job.type == job_type,
                    Job.dedupe_key == dedupe_key,
                )
            ).scalar_one_or_none()

        if existing is not None:
            if existing.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
                return existing.id
            existing.status = JobStatus.QUEUED
            existing.progress = 0
            existing.stage = "Queued"
            existing.error = None
            existing.error_details = {}
            existing.attempts = 0
            existing.payload = payload or existing.payload
            existing.parent_id = parent_id if parent_id is not None else existing.parent_id
            existing.user_id = user_id if user_id is not None else existing.user_id
            existing.priority = priority
            existing.locked_until = None
            existing.locked_by = None
            existing.next_run_at = next_run_at or now
            existing.max_attempts = max_attempts
            existing.started_at = None
            existing.finished_at = None
            session.flush()
            job_id = existing.id
        else:
            job = Job(
                type=job_type,
                payload=payload,
                source_id=source_id,
                parent_id=parent_id,
                user_id=user_id,
                priority=priority,
                idempotency_key=idempotency_key,
                next_run_at=next_run_at or now,
                max_attempts=max_attempts,
                dedupe_key=dedupe_key,
                status=JobStatus.QUEUED,
                error_details={},
            )
            session.add(job)
            session.flush()
            job_id = job.id

    emit(
        "job.created",
        job_id=job_id,
        type=str(job_type),
        source_id=source_id,
        parent_id=parent_id,
        user_id=user_id,
        priority=priority,
    )
    return job_id


def claim_next(worker_id: str = "worker-0", lease_seconds: int = DEFAULT_LEASE_SECONDS) -> ClaimedJob | None:
    """Atomically move one queued or lease-expired job to running with row-level locking."""
    now = utcnow()
    lease_expiry = now + dt.timedelta(seconds=lease_seconds)
    with session_scope() as session:
        bind = session.get_bind()
        is_postgres = "postgresql" in str(bind.url).lower() if bind else False

        if is_postgres:
            stmt = text(
                """
                WITH claimable AS (
                    SELECT id FROM jobs
                    WHERE (
                        status = 'queued'
                        OR (status = 'running' AND locked_until IS NOT NULL AND locked_until < :now)
                    )
                    AND parent_id IS NULL
                    AND (next_run_at IS NULL OR next_run_at <= :now)
                    ORDER BY priority DESC, id ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE jobs j
                   SET status = 'running',
                       started_at = COALESCE(j.started_at, :now),
                       locked_until = :lease_expiry,
                       locked_by = :worker_id,
                       attempts = j.attempts + 1
                  FROM claimable
                 WHERE j.id = claimable.id
             RETURNING j.id, j.type, j.payload, j.source_id, j.parent_id, j.attempts, j.user_id, j.priority, j.max_attempts
                """
            )
            row = session.execute(stmt, {"now": now, "lease_expiry": lease_expiry, "worker_id": worker_id}).fetchone()
        else:
            stmt = text(
                """
                UPDATE jobs
                   SET status = 'running',
                       started_at = COALESCE(started_at, :now),
                       locked_until = :lease_expiry,
                       locked_by = :worker_id,
                       attempts = attempts + 1
                 WHERE id = (
                     SELECT id FROM jobs
                      WHERE (status = 'queued' OR (status = 'running' AND locked_until IS NOT NULL AND locked_until < :now))
                        AND parent_id IS NULL
                        AND (next_run_at IS NULL OR next_run_at <= :now)
                      ORDER BY priority DESC, id ASC
                      LIMIT 1
                 )
             RETURNING id, type, payload, source_id, parent_id, attempts, user_id, priority, max_attempts
                """
            )
            row = session.execute(stmt, {"now": now, "lease_expiry": lease_expiry, "worker_id": worker_id}).fetchone()

        if row is None:
            return None

        raw_payload = row[2]
        payload = json.loads(raw_payload) if isinstance(raw_payload, str) else (raw_payload or {})
        return ClaimedJob(
            id=int(row[0]),
            type=JobType(row[1]),
            payload=payload,
            source_id=row[3],
            parent_id=row[4],
            attempts=int(row[5]),
            user_id=row[6],
            priority=int(row[7]) if row[7] is not None else 50,
            max_attempts=int(row[8]) if row[8] is not None else MAX_ATTEMPTS,
        )


def claim_next_specific(job_id: int, worker_id: str = "inline", lease_seconds: int = DEFAULT_LEASE_SECONDS) -> ClaimedJob | None:
    """Claim one named job, if it is claimable."""
    now = utcnow()
    lease_expiry = now + dt.timedelta(seconds=lease_seconds)
    with session_scope() as session:
        bind = session.get_bind()
        is_postgres = "postgresql" in str(bind.url).lower() if bind else False

        if is_postgres:
            stmt = text(
                """
                WITH claimable AS (
                    SELECT id FROM jobs
                    WHERE id = :job_id
                      AND (
                          status = 'queued'
                          OR (status = 'running' AND (locked_until IS NULL OR locked_until < :now))
                      )
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE jobs j
                   SET status = 'running',
                       started_at = COALESCE(j.started_at, :now),
                       locked_until = :lease_expiry,
                       locked_by = :worker_id,
                       attempts = j.attempts + 1
                  FROM claimable
                 WHERE j.id = claimable.id
             RETURNING j.id, j.type, j.payload, j.source_id, j.parent_id, j.attempts, j.user_id, j.priority, j.max_attempts
                """
            )
            row = session.execute(stmt, {"job_id": job_id, "now": now, "lease_expiry": lease_expiry, "worker_id": worker_id}).fetchone()
        else:
            stmt = text(
                """
                UPDATE jobs
                   SET status = 'running',
                       started_at = COALESCE(started_at, :now),
                       locked_until = :lease_expiry,
                       locked_by = :worker_id,
                       attempts = attempts + 1
                 WHERE id = :job_id
                   AND (status = 'queued' OR (status = 'running' AND (locked_until IS NULL OR locked_until < :now)))
             RETURNING id, type, payload, source_id, parent_id, attempts, user_id, priority, max_attempts
                """
            )
            row = session.execute(stmt, {"job_id": job_id, "now": now, "lease_expiry": lease_expiry, "worker_id": worker_id}).fetchone()

        if row is None:
            return None
        raw_payload = row[2]
        payload = json.loads(raw_payload) if isinstance(raw_payload, str) else (raw_payload or {})
        return ClaimedJob(
            id=int(row[0]),
            type=JobType(row[1]),
            payload=payload,
            source_id=row[3],
            parent_id=row[4],
            attempts=int(row[5]),
            user_id=row[6],
            priority=int(row[7]) if row[7] is not None else 50,
            max_attempts=int(row[8]) if row[8] is not None else MAX_ATTEMPTS,
        )


def heartbeat(job_id: int, worker_id: str, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> bool:
    """Extend lease on a running job while processing."""
    new_expiry = utcnow() + dt.timedelta(seconds=lease_seconds)
    with session_scope() as session:
        result = session.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == JobStatus.RUNNING, Job.locked_by == worker_id)
            .values(locked_until=new_expiry)
        )
        return (result.rowcount or 0) > 0


def set_progress(job_id: int, progress: int, stage: str = "") -> None:
    clamped = max(0, min(100, int(progress)))
    user_id = None
    with session_scope() as session:
        values: dict[str, Any] = {"progress": clamped}
        if stage:
            values["stage"] = stage
        session.execute(update(Job).where(Job.id == job_id).values(**values))
        job = session.get(Job, job_id)
        if job:
            user_id = job.user_id
    emit("job.progress", job_id=job_id, progress=clamped, stage=stage, user_id=user_id)


def mark_succeeded(job_id: int, stage: str = "Done", payload_updates: dict[str, Any] | None = None) -> None:
    user_id = None
    source_id = None
    with session_scope() as session:
        job = session.get(Job, job_id)
        if job is None:
            return
        job.status = JobStatus.SUCCEEDED
        job.progress = 100
        job.stage = stage
        job.error = None
        job.finished_at = utcnow()
        job.locked_until = None
        job.locked_by = None
        if payload_updates:
            current_payload = dict(job.payload or {})
            current_payload.update(payload_updates)
            job.payload = current_payload
        source_id = job.source_id
        user_id = job.user_id
    emit("job.succeeded", job_id=job_id, source_id=source_id, stage=stage, user_id=user_id)


def mark_failed(
    job_id: int,
    error: str,
    *,
    retryable: bool = True,
    error_details: dict[str, Any] | None = None,
) -> bool:
    """Record a failure with exponential backoff if retryable."""
    now = utcnow()
    error_details = error_details or {}
    user_id = None
    source_id = None
    with session_scope() as session:
        job = session.get(Job, job_id)
        if job is None:
            return False
        max_att = job.max_attempts or MAX_ATTEMPTS
        will_retry = retryable and job.attempts < max_att

        job.locked_until = None
        job.locked_by = None
        job.error = error[:4000]
        job.error_details = error_details

        if will_retry:
            backoff_sec = min(300, 5 * (2 ** max(0, job.attempts - 1)))
            job.status = JobStatus.QUEUED
            job.next_run_at = now + dt.timedelta(seconds=backoff_sec)
            job.stage = f"Retrying ({job.attempts}/{max_att}) in {backoff_sec}s"
            job.progress = 0
        else:
            job.status = JobStatus.FAILED
            job.finished_at = now
            job.stage = "Failed"

        source_id = job.source_id
        attempts = job.attempts
        user_id = job.user_id

    if will_retry:
        log.warning("job %s failed (attempt %s/%s), requeued: %s", job_id, attempts, max_att, error)
        emit(
            "job.progress",
            job_id=job_id,
            progress=0,
            stage=f"Retrying ({attempts}/{max_att})",
            user_id=user_id,
        )
    else:
        log.error("job %s failed permanently: %s", job_id, error)
        emit("job.failed", job_id=job_id, source_id=source_id, error=error[:2000], user_id=user_id)
    return will_retry


def cancel(job_id: int) -> bool:
    """Cancel a queued job, or flag a running one for cooperative cancellation."""
    user_id = None
    with session_scope() as session:
        job = session.get(Job, job_id)
        if job is None or job.status in {
            JobStatus.SUCCEEDED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        }:
            return False
        job.status = JobStatus.CANCELLED
        job.finished_at = utcnow()
        job.stage = "Cancelled"
        job.locked_until = None
        job.locked_by = None
        user_id = job.user_id

        session.execute(
            update(Job)
            .where(Job.parent_id == job_id, Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]))
            .values(status=JobStatus.CANCELLED, finished_at=utcnow(), stage="Cancelled", locked_until=None, locked_by=None)
        )
    emit("job.cancelled", job_id=job_id, user_id=user_id)
    return True


def is_cancelled(job_id: int) -> bool:
    """Cooperative cancellation check, polled by long-running stages."""
    with session_scope() as session:
        status = session.execute(select(Job.status).where(Job.id == job_id)).scalar_one_or_none()
    return status == JobStatus.CANCELLED


def retry(job_id: int) -> bool:
    """Manually re-enqueue a failed or cancelled job."""
    user_id = None
    with session_scope() as session:
        job = session.get(Job, job_id)
        if job is None or job.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
            return False
        job.status = JobStatus.QUEUED
        job.attempts = 0
        job.progress = 0
        job.stage = "Queued"
        job.error = None
        job.error_details = {}
        job.started_at = None
        job.finished_at = None
        job.locked_until = None
        job.locked_by = None
        job.next_run_at = utcnow()
        user_id = job.user_id
    emit("job.progress", job_id=job_id, progress=0, stage="Queued", user_id=user_id)
    return True


def recover_orphans(worker_id: str | None = None) -> int:
    """Recover jobs stranded in running with expired leases."""
    now = utcnow()
    with session_scope() as session:
        stmt = select(Job).where(
            Job.status == JobStatus.RUNNING,
            (Job.locked_until.is_(None) | (Job.locked_until < now))
        )
        stranded = list(session.execute(stmt).scalars())
        requeued = 0
        for job in stranded:
            job.locked_until = None
            job.locked_by = None
            max_att = job.max_attempts or MAX_ATTEMPTS
            if job.attempts >= max_att:
                job.status = JobStatus.FAILED
                job.error = "Exceeded retry limit after timeout/restart."
                job.finished_at = now
            else:
                job.status = JobStatus.QUEUED
                job.progress = 0
                job.stage = "Requeued after lease expiry"
                job.started_at = None
                job.next_run_at = now
                requeued += 1
    if stranded:
        log.info("recovered %d interrupted job(s), %d requeued", len(stranded), requeued)
    return requeued


def queue_depth() -> int:
    with session_scope() as session:
        return int(
            session.execute(
                select(func.count()).select_from(Job).where(Job.status == JobStatus.QUEUED)
            ).scalar_one()
        )


def list_jobs(
    *,
    limit: int = 50,
    active_only: bool = False,
    user_id: int | None = None,
    status: str | None = None,
    job_type: str | None = None,
) -> list[dict[str, Any]]:
    with session_scope() as session:
        stmt = select(Job).order_by(Job.id.desc())
        if user_id is not None:
            stmt = stmt.where((Job.user_id == user_id) | (Job.user_id.is_(None)))
        if active_only:
            stmt = stmt.where(Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]))
        elif status:
            stmt = stmt.where(Job.status == status)
        if job_type:
            stmt = stmt.where(Job.type == job_type)
        stmt = stmt.limit(limit)
        return [_job_dict(job) for job in session.execute(stmt).scalars()]


def get_job(job_id: int) -> dict[str, Any] | None:
    with session_scope() as session:
        job = session.get(Job, job_id)
        return _job_dict(job) if job else None


def _iso(value: dt.datetime | None) -> str | None:
    return value.isoformat() if value else None


def _job_dict(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "user_id": job.user_id,
        "parent_id": job.parent_id,
        "source_id": job.source_id,
        "type": str(job.type),
        "status": str(job.status),
        "priority": job.priority,
        "idempotency_key": job.idempotency_key,
        "progress": job.progress,
        "stage": job.stage,
        "error": job.error,
        "error_details": job.error_details or {},
        "payload": job.payload or {},
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "locked_until": _iso(job.locked_until),
        "locked_by": job.locked_by,
        "next_run_at": _iso(job.next_run_at),
        "created_at": _iso(job.created_at),
        "started_at": _iso(job.started_at),
        "finished_at": _iso(job.finished_at),
    }
