"""Activity logging utility for tracking student learning events in EduVerse AI."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from .db.models import ActivityLog

log = logging.getLogger(__name__)


def record_activity(
    session: Session,
    action: str,
    entity_type: str,
    title: str,
    entity_id: int | None = None,
    user_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> ActivityLog:
    """Persist an activity event to the database."""
    try:
        activity = ActivityLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            title=title,
            details=details or {},
        )
        session.add(activity)
        session.flush()
        return activity
    except Exception as exc:
        log.warning("Failed to record activity log: %s", exc)
        return None  # Non-fatal
