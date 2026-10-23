"""Revision Planner API endpoints for EduVerse AI."""

from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..activity import record_activity
from ..auth import get_optional_user
from ..db.models import RevisionSession, User
from ..db.session import get_db
from ..db.types import utcnow
from ..errors import ForbiddenError
from ..study.revision_planner import generate_revision_recommendations

router = APIRouter(prefix="/revision-planner", tags=["revision-planner"])


class RecommendationOut(BaseModel):
    topic: str
    priority: str
    recommended_duration_min: int
    reason: str
    source_id: int | None
    concept_id: int | None


class ScheduleSessionRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=255)
    priority: str = Field(default="MEDIUM", pattern="^(HIGH|MEDIUM|LOW)$")
    recommended_duration_min: int = Field(default=20, ge=5, le=180)
    reason: str = Field(default="")
    source_id: int | None = None
    concept_id: int | None = None
    scheduled_date: dt.datetime | None = None


class UpdateSessionRequest(BaseModel):
    status: str | None = Field(default=None, pattern="^(PENDING|COMPLETED|SKIPPED)$")
    notes: str | None = None


class RevisionSessionOut(BaseModel):
    id: int
    user_id: int | None
    source_id: int | None
    concept_id: int | None
    topic: str
    priority: str
    recommended_duration_min: int
    reason: str
    status: str
    scheduled_date: dt.datetime
    completed_at: dt.datetime | None
    notes: str | None
    created_at: dt.datetime

    model_config = {"from_attributes": True}


@router.get("/recommendations", response_model=list[RecommendationOut])
def get_recommendations(db: Session = Depends(get_db)) -> list[RecommendationOut]:
    """Generate dynamic adaptive revision recommendations."""
    recs = generate_revision_recommendations(db)
    return [
        RecommendationOut(
            topic=r.topic,
            priority=r.priority,
            recommended_duration_min=r.recommended_duration_min,
            reason=r.reason,
            source_id=r.source_id,
            concept_id=r.concept_id,
        )
        for r in recs
    ]


@router.post("/schedule", response_model=RevisionSessionOut, status_code=status.HTTP_201_CREATED)
def schedule_session(
    req: ScheduleSessionRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> RevisionSessionOut:
    """Schedule and persist a new revision session."""
    user_id = user.id if user else None
    session_obj = RevisionSession(
        user_id=user_id,
        source_id=req.source_id,
        concept_id=req.concept_id,
        topic=req.topic,
        priority=req.priority,
        recommended_duration_min=req.recommended_duration_min,
        reason=req.reason,
        status="PENDING",
        scheduled_date=req.scheduled_date or utcnow(),
    )
    db.add(session_obj)
    db.flush()

    record_activity(
        session=db,
        action="REVISION_SCHEDULED",
        entity_type="revision",
        entity_id=session_obj.id,
        title=f"Scheduled revision: {session_obj.topic}",
        user_id=user_id,
    )

    return RevisionSessionOut.model_validate(session_obj)


@router.get("/sessions", response_model=list[RevisionSessionOut])
def list_sessions(
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> list[RevisionSessionOut]:
    """List scheduled revision sessions, optionally filtered by status."""
    stmt = select(RevisionSession)
    if user is not None:
        stmt = stmt.where(RevisionSession.user_id == user.id)
    if status_filter:
        stmt = stmt.where(RevisionSession.status == status_filter.upper())
    stmt = stmt.order_by(RevisionSession.scheduled_date.asc())
    sessions = db.scalars(stmt).all()
    return [RevisionSessionOut.model_validate(s) for s in sessions]


@router.patch("/sessions/{session_id}", response_model=RevisionSessionOut)
def update_session(
    session_id: int,
    req: UpdateSessionRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> RevisionSessionOut:
    """Update revision session status (mark completed/skipped) or add notes."""
    session_obj = db.get(RevisionSession, session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="Revision session not found.")
    if session_obj.user_id is not None and user is not None and session_obj.user_id != user.id:
        raise ForbiddenError("You do not have permission to update this revision session.")

    if req.status:
        session_obj.status = req.status
        if req.status == "COMPLETED" and not session_obj.completed_at:
            session_obj.completed_at = utcnow()
            record_activity(
                session=db,
                action="REVISION_COMPLETED",
                entity_type="revision",
                entity_id=session_obj.id,
                title=f"Completed revision: {session_obj.topic}",
                user_id=user.id if user else session_obj.user_id,
            )

    if req.notes is not None:
        session_obj.notes = req.notes

    db.flush()
    return RevisionSessionOut.model_validate(session_obj)


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> dict[str, str]:
    """Delete a scheduled revision session."""
    session_obj = db.get(RevisionSession, session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="Revision session not found.")
    if session_obj.user_id is not None and user is not None and session_obj.user_id != user.id:
        raise ForbiddenError("You do not have permission to delete this revision session.")
    db.delete(session_obj)
    db.flush()
    return {"message": "Revision session deleted."}
