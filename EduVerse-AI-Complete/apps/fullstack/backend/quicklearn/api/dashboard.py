"""Student Dashboard API endpoints for EduVerse AI.

Provides comprehensive live learning metrics, quiz statistics, FSRS retention health,
knowledge gaps, and a real chronological activity stream.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import get_optional_user
from ..db.models import (
    ActivityLog,
    Card,
    Concept,
    Note,
    QuizAttempt,
    QuizSession,
    RevisionSession,
    Source,
    User,
)
from ..db.session import get_db
from ..db.types import utcnow
from ..study.knowledge_gap import analyze_knowledge_gaps

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class SourceBrief(BaseModel):
    id: int
    title: str
    kind: str
    created_at: dt.datetime


class ActivityItemOut(BaseModel):
    id: int
    action: str
    entity_type: str
    title: str
    details: dict[str, Any]
    created_at: dt.datetime


class DashboardStatsOut(BaseModel):
    # Documents / Courses
    total_sources: int
    recent_sources: list[SourceBrief]
    # Spaced Repetition (FSRS-6)
    total_cards: int
    cards_due_today: int
    cards_mastered: int
    cards_learning: int
    # Quiz Performance
    total_quiz_sessions: int
    total_quiz_attempts: int
    average_quiz_accuracy: float
    quizzes_passed_pct: float
    # Knowledge Gaps
    critical_gaps_count: int
    moderate_gaps_count: int
    # Revision Sessions
    pending_revision_count: int
    completed_revision_count: int
    # Notes
    total_notes: int
    # Real Activity Stream
    recent_activities: list[ActivityItemOut]


@router.get("/stats", response_model=DashboardStatsOut)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> DashboardStatsOut:
    """Aggregate real learning analytics from the database."""
    now = utcnow()

    # 1. Sources / Study Materials (User Scoped)
    src_query = select(Source)
    if user is not None:
        src_query = src_query.where((Source.user_id == user.id) | (Source.user_id.is_(None)))
    else:
        src_query = src_query.where(Source.user_id.is_(None))
    sources = db.scalars(src_query.order_by(Source.created_at.desc())).all()
    total_sources = len(sources)
    recent_sources = [
        SourceBrief(
            id=s.id,
            title=s.title,
            kind=s.kind.value if hasattr(s.kind, "value") else str(s.kind),
            created_at=s.created_at,
        )
        for s in sources[:5]
    ]

    # 2. Flashcards & Spaced Repetition (User Scoped)
    card_query = select(Card).join(Source, Source.id == Card.source_id)
    if user is not None:
        card_query = card_query.where((Source.user_id == user.id) | (Source.user_id.is_(None)))
    else:
        card_query = card_query.where(Source.user_id.is_(None))
    cards = db.scalars(card_query).all()
    total_cards = len(cards)
    cards_due_today = sum(1 for c in cards if c.due <= now and not c.suspended)
    cards_mastered = sum(
        1 for c in cards if (c.stability and c.stability >= 5.0) or c.reps >= 3
    )
    cards_learning = total_cards - cards_mastered

    # 3. Quiz Attempts & Performance
    total_quiz_sessions = db.scalar(select(func.count(QuizSession.id))) or 0
    attempts = db.scalars(select(QuizAttempt)).all()
    total_quiz_attempts = len(attempts)
    correct_attempts = sum(1 for a in attempts if a.is_correct)
    avg_accuracy = (
        round((correct_attempts / total_quiz_attempts) * 100.0, 1)
        if total_quiz_attempts > 0
        else 0.0
    )
    passed_attempts = sum(1 for a in attempts if a.score >= 0.6 or a.is_correct)
    pass_pct = (
        round((passed_attempts / total_quiz_attempts) * 100.0, 1)
        if total_quiz_attempts > 0
        else 0.0
    )

    # 4. Knowledge Gaps
    gap_summary = analyze_knowledge_gaps(db)
    critical_gaps = gap_summary.critical_gaps_count
    moderate_gaps = gap_summary.moderate_gaps_count

    # 5. Revision Sessions (User Scoped)
    rev_query = select(RevisionSession)
    if user is not None:
        rev_query = rev_query.where((RevisionSession.user_id == user.id) | (RevisionSession.user_id.is_(None)))
    else:
        rev_query = rev_query.where(RevisionSession.user_id.is_(None))
    revision_sessions = db.scalars(rev_query).all()
    pending_revisions = sum(1 for r in revision_sessions if r.status == "PENDING")
    completed_revisions = sum(1 for r in revision_sessions if r.status == "COMPLETED")

    # 6. Notes (User Scoped)
    note_query = select(func.count(Note.id))
    if user is not None:
        note_query = note_query.where((Note.user_id == user.id) | (Note.user_id.is_(None)))
    else:
        note_query = note_query.where(Note.user_id.is_(None))
    total_notes = db.scalar(note_query) or 0

    # 7. Real Activity Stream from ActivityLog + Fallback to entities
    logged_activities = db.scalars(
        select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(10)
    ).all()

    activity_items: list[ActivityItemOut] = []
    if logged_activities:
        activity_items = [
            ActivityItemOut(
                id=a.id,
                action=a.action,
                entity_type=a.entity_type,
                title=a.title,
                details=a.details or {},
                created_at=a.created_at,
            )
            for a in logged_activities
        ]
    else:
        # Construct synthetic activity stream from actual DB entities
        for s in sources[:3]:
            activity_items.append(
                ActivityItemOut(
                    id=s.id,
                    action="DOCUMENT_UPLOADED",
                    entity_type="source",
                    title=f"Uploaded: {s.title}",
                    details={"filename": s.original_filename or s.title},
                    created_at=s.created_at,
                )
            )
        for a in attempts[-3:]:
            item_q = a.item.question if a.item else "Quiz item"
            activity_items.append(
                ActivityItemOut(
                    id=a.id,
                    action="QUIZ_COMPLETED",
                    entity_type="quiz",
                    title=f"Quiz Attempt: {'Correct' if a.is_correct else 'Incorrect'}",
                    details={"question": item_q[:60]},
                    created_at=a.attempted_at,
                )
            )

    # Sort activity items by date
    activity_items.sort(key=lambda x: x.created_at, reverse=True)

    return DashboardStatsOut(
        total_sources=total_sources,
        recent_sources=recent_sources,
        total_cards=total_cards,
        cards_due_today=cards_due_today,
        cards_mastered=cards_mastered,
        cards_learning=cards_learning,
        total_quiz_sessions=total_quiz_sessions,
        total_quiz_attempts=total_quiz_attempts,
        average_quiz_accuracy=avg_accuracy,
        quizzes_passed_pct=pass_pct,
        critical_gaps_count=critical_gaps,
        moderate_gaps_count=moderate_gaps,
        pending_revision_count=pending_revisions,
        completed_revision_count=completed_revisions,
        total_notes=total_notes,
        recent_activities=activity_items[:10],
    )
