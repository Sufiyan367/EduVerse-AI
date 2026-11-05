"""In-process asyncio worker pool with resource concurrency management and lease heartbeats.

Enforces:
- Max 1 concurrent local LLM generation job to preserve GPU VRAM on RTX 3050.
- Max 2 concurrent CPU/data jobs.
- Row-level lease heartbeats every 30s.
- Automatic backoff when Ollama is busy/restarting.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ..config import Config, get_config
from ..db.enums import JobType
from ..errors import CancelledError, QuicklearnError
from . import queue as jq
from .events import emit, get_bus

log = logging.getLogger(__name__)

IDLE_POLL_SEC = 0.35
RETRY_BACKOFF_SEC = (1.0, 4.0, 12.0)

# Resource semaphores
_llm_semaphore = asyncio.Semaphore(1)
_data_semaphore = asyncio.Semaphore(2)

LLM_JOB_TYPES = {
    JobType.GENERATE_NOTES,
    JobType.GENERATE_CONCEPTS,
    JobType.GENERATE_CARDS,
    JobType.GENERATE_QUIZ,
    JobType.AUTONOMOUS_SYLLABUS,
    JobType.AUTONOMOUS_PAPER,
    JobType.AUTONOMOUS_EXAM_EVAL,
}


@dataclass(slots=True)
class JobContext:
    """Handed to every handler. The primary interface for progress and cancellation."""

    job_id: int
    job_type: JobType
    payload: dict[str, Any]
    source_id: int | None
    attempts: int
    user_id: int | None = None
    priority: int = 50
    _percent: int = 0

    def progress(self, percent: int, stage: str = "") -> None:
        self._percent = max(0, min(100, int(percent)))
        jq.set_progress(self.job_id, self._percent, stage)

    def stage(self, stage: str) -> None:
        """Update the stage label, holding the current percentage."""
        jq.set_progress(self.job_id, self._percent, stage)

    def check_cancelled(self) -> None:
        """Raise if the user cancelled. Call between units of work in long stages."""
        if jq.is_cancelled(self.job_id):
            raise CancelledError("Job cancelled by user")

    def sub_progress(self, base: int, span: int, done: int, total: int, stage: str = "") -> None:
        if total <= 0:
            return
        self.progress(base + int(span * (done / total)), stage)


Handler = Callable[[JobContext], Awaitable[None]]
_handlers: dict[JobType, Handler] = {}


def register(job_type: JobType) -> Callable[[Handler], Handler]:
    def decorator(fn: Handler) -> Handler:
        _handlers[job_type] = fn
        return fn

    return decorator


def get_handler(job_type: JobType) -> Handler | None:
    return _handlers.get(job_type)


def registered_types() -> list[JobType]:
    return sorted(_handlers, key=str)


class WorkerPool:
    def __init__(self, config: Config | None = None) -> None:
        self._config = config or get_config()
        self._tasks: list[asyncio.Task[None]] = []
        self._stopping = asyncio.Event()
        self._active: dict[int, int] = {}

    @property
    def active_job_ids(self) -> list[int]:
        return list(self._active.values())

    async def start(self) -> None:
        # Import handlers for registration side-effects
        from .. import handlers  # noqa: F401
        try:
            from .. import automation  # noqa: F401
        except ImportError:
            pass

        get_bus().bind_loop(asyncio.get_running_loop())

        recovered = await asyncio.to_thread(jq.recover_orphans)
        if recovered:
            log.info("requeued %d job(s) interrupted by a previous shutdown", recovered)

        count = max(1, self._config.worker_concurrency)
        self._stopping.clear()
        for index in range(count):
            self._tasks.append(asyncio.create_task(self._loop(index), name=f"worker-{index}"))
        log.info(
            "worker pool started with %d task(s); handlers: %s",
            count,
            ", ".join(str(t) for t in registered_types()),
        )

    async def stop(self) -> None:
        self._stopping.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _loop(self, index: int) -> None:
        worker_id = f"worker-{index}"
        while not self._stopping.is_set():
            try:
                job = await asyncio.to_thread(jq.claim_next, worker_id=worker_id)
            except Exception:
                log.exception("worker %s failed to claim a job", index)
                await asyncio.sleep(1.0)
                continue

            if job is None:
                await asyncio.sleep(IDLE_POLL_SEC + random.random() * 0.15)
                continue

            self._active[index] = job.id
            try:
                await self._run(job, worker_id=worker_id)
            finally:
                self._active.pop(index, None)

    async def _run(self, job: jq.ClaimedJob, worker_id: str = "worker-0") -> None:
        handler = get_handler(job.type)
        if handler is None:
            await asyncio.to_thread(
                jq.mark_failed,
                job.id,
                f"No handler registered for job type '{job.type}'. This is a bug.",
                retryable=False,
                error_details={"code": "HANDLER_MISSING"},
            )
            return

        ctx = JobContext(
            job_id=job.id,
            job_type=job.type,
            payload=job.payload,
            source_id=job.source_id,
            attempts=job.attempts,
            user_id=job.user_id,
            priority=job.priority,
        )

        log.info("job %s (%s) starting, attempt %s", job.id, job.type, job.attempts)

        # Background heartbeat loop during execution
        heartbeat_stop = asyncio.Event()

        async def _heartbeat_loop():
            while not heartbeat_stop.is_set():
                try:
                    await asyncio.sleep(30)
                    if heartbeat_stop.is_set():
                        break
                    await asyncio.to_thread(jq.heartbeat, job.id, worker_id)
                except asyncio.CancelledError:
                    break
                except Exception as err:
                    log.debug("Heartbeat error on job %s: %s", job.id, err)

        heartbeat_task = asyncio.create_task(_heartbeat_loop())

        # Select semaphore depending on whether job uses LLM
        sem = _llm_semaphore if job.type in LLM_JOB_TYPES else _data_semaphore

        try:
            async with sem:
                await handler(ctx)
        except CancelledError:
            log.info("job %s cancelled", job.id)
            return
        except asyncio.CancelledError:
            log.info("job %s interrupted by shutdown", job.id)
            raise
        except QuicklearnError as exc:
            requeued = await asyncio.to_thread(
                jq.mark_failed,
                job.id,
                exc.message,
                retryable=exc.retryable,
                error_details={"error_code": type(exc).__name__, "retryable": exc.retryable},
            )
            if requeued:
                await asyncio.sleep(
                    RETRY_BACKOFF_SEC[min(job.attempts - 1, len(RETRY_BACKOFF_SEC) - 1)]
                )
            return
        except Exception as exc:
            log.exception("job %s crashed", job.id)
            err_msg = str(exc)
            is_ollama_err = "connection refused" in err_msg.lower() or "ollama" in err_msg.lower()
            await asyncio.to_thread(
                jq.mark_failed,
                job.id,
                f"{type(exc).__name__}: {exc}",
                retryable=True,
                error_details={
                    "error_type": type(exc).__name__,
                    "is_ollama_error": is_ollama_err,
                },
            )
            return
        finally:
            heartbeat_stop.set()
            heartbeat_task.cancel()

        if await asyncio.to_thread(jq.is_cancelled, job.id):
            return
        await asyncio.to_thread(jq.mark_succeeded, job.id)
        log.info("job %s (%s) finished", job.id, job.type)


_pool: WorkerPool | None = None


def get_pool() -> WorkerPool:
    global _pool
    if _pool is None:
        _pool = WorkerPool()
    return _pool


async def run_job_inline(job_id: int) -> None:
    """Execute a queued job immediately on the current loop, bypassing the pool."""
    job = await asyncio.to_thread(jq.claim_next_specific, job_id, worker_id="inline")
    if job is None:
        return
    pool = WorkerPool()
    await pool._run(job, worker_id="inline")


def reset_pool() -> None:
    global _pool
    _pool = None


__all__ = [
    "JobContext",
    "WorkerPool",
    "emit",
    "get_handler",
    "get_pool",
    "register",
    "registered_types",
    "reset_pool",
    "run_job_inline",
]
