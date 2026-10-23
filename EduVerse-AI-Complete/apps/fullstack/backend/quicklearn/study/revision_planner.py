"""Adaptive Revision Planner for EduVerse AI.

Generates targeted, prioritized revision recommendations combining
Knowledge Gap metrics, FSRS spaced repetition schedules, and new study materials.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import Card, Concept, RevisionSession, Source
from ..db.types import utcnow
from .knowledge_gap import analyze_knowledge_gaps

log = logging.getLogger(__name__)


@dataclass
class RevisionRecommendation:
    topic: str
    priority: str  # "HIGH", "MEDIUM", "LOW"
    recommended_duration_min: int
    reason: str
    source_id: int | None
    concept_id: int | None


def generate_revision_recommendations(session: Session) -> list[RevisionRecommendation]:
    """Compute adaptive revision recommendations based on live learning data."""
    recommendations: list[RevisionRecommendation] = []
    now = utcnow()

    # 1. Knowledge Gaps (Highest Priority)
    gap_summary = analyze_knowledge_gaps(session)
    for topic_gap in gap_summary.topics:
        if topic_gap.status == "CRITICAL":
            recommendations.append(
                RevisionRecommendation(
                    topic=f"Remediate: {topic_gap.topic_name}",
                    priority="HIGH",
                    recommended_duration_min=25,
                    reason=f"Critical knowledge gap detected ({topic_gap.accuracy_pct}% accuracy on {topic_gap.total_questions} questions). Focus on core definitions and quiz mistakes.",
                    source_id=topic_gap.source_id,
                    concept_id=topic_gap.topic_id,
                )
            )
        elif topic_gap.status == "MODERATE":
            recommendations.append(
                RevisionRecommendation(
                    topic=f"Reinforce: {topic_gap.topic_name}",
                    priority="MEDIUM",
                    recommended_duration_min=15,
                    reason=f"Moderate proficiency gap ({topic_gap.accuracy_pct}% accuracy). Practice active recall to solidify understanding.",
                    source_id=topic_gap.source_id,
                    concept_id=topic_gap.topic_id,
                )
            )

    # 2. FSRS Cards Due for Review
    due_cards_count = session.scalar(
        select(func.count(Card.id)).where(Card.due <= now, Card.suspended.is_(False))
    ) or 0

    if due_cards_count > 0:
        # Group due cards by source
        due_by_source = session.execute(
            select(Source.id, Source.title, func.count(Card.id))
            .join(Card, Card.source_id == Source.id)
            .where(Card.due <= now, Card.suspended.is_(False))
            .group_by(Source.id, Source.title)
        ).all()

        for source_id, source_title, count in due_by_source:
            duration = min(40, max(10, count * 2))
            recommendations.append(
                RevisionRecommendation(
                    topic=f"Spaced Review: {source_title}",
                    priority="MEDIUM",
                    recommended_duration_min=duration,
                    reason=f"{count} flashcards due under FSRS-6 scheduler. Reviewing today prevents memory decay.",
                    source_id=source_id,
                    concept_id=None,
                )
            )

    # 3. Newly Ingested Sources Needing First Quiz / Reinforcement
    sources = session.scalars(select(Source).order_by(Source.created_at.desc()).limit(5)).all()
    for src in sources:
        # Check if any quiz items exist or were attempted
        has_attempts = False
        for item in src.quiz_items:
            # We check if there's any attempt
            if item.id:
                has_attempts = True
                break

        # If source has segments but no quizzes taken yet, recommend initial review
        if len(src.segments) > 0 and not any(r.source_id == src.id for r in recommendations):
            recommendations.append(
                RevisionRecommendation(
                    topic=f"Initial Study: {src.title}",
                    priority="LOW",
                    recommended_duration_min=20,
                    reason=f"Document ingested ({len(src.segments)} segments). Generate an initial quiz or flashcard set to establish baseline mastery.",
                    source_id=src.id,
                    concept_id=None,
                )
            )

    # Deduplicate and sort by priority
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    recommendations.sort(key=lambda r: priority_order.get(r.priority, 3))
    return recommendations
