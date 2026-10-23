"""Knowledge Gap Detector for EduVerse AI.

Algorithmic, evidence-based identification of conceptual weaknesses from
actual quiz attempt history and spaced repetition lapses.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Card, CardState, Concept, QuizAttempt, QuizItem, Source

log = logging.getLogger(__name__)


@dataclass
class FailureEvidence:
    question: str
    user_answer: str
    correct_answer: str
    explanation: str


@dataclass
class TopicGap:
    topic_id: int | None
    topic_name: str
    source_id: int | None
    source_title: str | None
    definition: str
    total_questions: int
    correct_questions: int
    accuracy_pct: float
    status: str  # "CRITICAL", "MODERATE", "PROFICIENT", "MASTERED"
    evidence: list[FailureEvidence] = field(default_factory=list)


@dataclass
class KnowledgeGapSummary:
    total_evaluated_topics: int
    critical_gaps_count: int
    moderate_gaps_count: int
    mastered_count: int
    overall_accuracy_pct: float
    topics: list[TopicGap] = field(default_factory=list)


def analyze_knowledge_gaps(session: Session) -> KnowledgeGapSummary:
    """Analyze all recorded quiz attempts and concept mastery to surface knowledge gaps."""
    # 1. Fetch all quiz attempts with their associated items
    attempts = session.scalars(select(QuizAttempt)).all()

    # Topic aggregator: key is (concept_id, topic_name)
    topic_stats: dict[str, dict[str, Any]] = {}

    for attempt in attempts:
        item: QuizItem | None = attempt.item
        if not item:
            continue

        # Determine topic name
        topic_name = "General Knowledge"
        concept_def = ""
        source_title = item.source.title if item.source else "Independent Topic"
        source_id = item.source_id
        concept_id = item.concept_id

        if item.concept:
            topic_name = item.concept.name
            concept_def = item.concept.definition or ""
        elif item.source:
            topic_name = item.source.title

        key = f"{concept_id}:{topic_name}"

        if key not in topic_stats:
            topic_stats[key] = {
                "concept_id": concept_id,
                "topic_name": topic_name,
                "source_id": source_id,
                "source_title": source_title,
                "definition": concept_def,
                "total": 0,
                "correct": 0,
                "evidence": [],
            }

        topic_stats[key]["total"] += 1
        if attempt.is_correct:
            topic_stats[key]["correct"] += 1
        else:
            topic_stats[key]["evidence"].append(
                FailureEvidence(
                    question=item.question,
                    user_answer=attempt.response or "(blank)",
                    correct_answer=item.answer,
                    explanation=item.explanation or "",
                )
            )

    # Also factor in concepts with cards that have lapsed frequently
    lapsed_cards = session.scalars(
        select(Card).where(Card.state == CardState.RELEARNING)
    ).all()
    for card in lapsed_cards:
        if card.concept:
            key = f"{card.concept_id}:{card.concept.name}"
            if key in topic_stats:
                topic_stats[key]["total"] += card.lapses
            else:
                topic_stats[key] = {
                    "concept_id": card.concept_id,
                    "topic_name": card.concept.name,
                    "source_id": card.source_id,
                    "source_title": card.source.title if card.source else None,
                    "definition": card.concept.definition or "",
                    "total": card.lapses,
                    "correct": 0,
                    "evidence": [
                        FailureEvidence(
                            question=f"Flashcard lapse: {card.front[:80]}...",
                            user_answer="Recalled incorrectly in FSRS review",
                            correct_answer=card.back[:80],
                            explanation="Card entered relearning state due to recall difficulty.",
                        )
                    ],
                }

    # If no quiz attempts exist yet, populate from available concepts as "UNTESTED / NEEDING PRACTICE"
    if not topic_stats:
        concepts = session.scalars(select(Concept).limit(10)).all()
        for concept in concepts:
            key = f"{concept.id}:{concept.name}"
            topic_stats[key] = {
                "concept_id": concept.id,
                "topic_name": concept.name,
                "source_id": concept.source_id,
                "source_title": concept.source.title if concept.source else None,
                "definition": concept.definition or "",
                "total": 0,
                "correct": 0,
                "evidence": [],
            }

    # Transform into TopicGap objects
    gaps: list[TopicGap] = []
    total_q = 0
    total_c = 0

    for key, data in topic_stats.items():
        tot = data["total"]
        cor = data["correct"]
        total_q += tot
        total_c += cor

        if tot == 0:
            acc = 0.0
            status_val = "UNTESTED"
        else:
            acc = round((cor / tot) * 100.0, 1)
            if acc < 50.0:
                status_val = "CRITICAL"
            elif acc < 70.0:
                status_val = "MODERATE"
            elif acc < 90.0:
                status_val = "PROFICIENT"
            else:
                status_val = "MASTERED"

        gaps.append(
            TopicGap(
                topic_id=data["concept_id"],
                topic_name=data["topic_name"],
                source_id=data["source_id"],
                source_title=data["source_title"],
                definition=data["definition"],
                total_questions=tot,
                correct_questions=cor,
                accuracy_pct=acc,
                status=status_val,
                evidence=data["evidence"],
            )
        )

    # Sort gaps by urgency: CRITICAL first, then MODERATE, then UNTESTED, then others
    urgency_order = {"CRITICAL": 0, "MODERATE": 1, "UNTESTED": 2, "PROFICIENT": 3, "MASTERED": 4}
    gaps.sort(key=lambda g: (urgency_order.get(g.status, 5), g.accuracy_pct))

    critical_count = sum(1 for g in gaps if g.status == "CRITICAL")
    moderate_count = sum(1 for g in gaps if g.status == "MODERATE")
    mastered_count = sum(1 for g in gaps if g.status == "MASTERED")
    overall_acc = round((total_c / total_q) * 100.0, 1) if total_q > 0 else 0.0

    return KnowledgeGapSummary(
        total_evaluated_topics=len(gaps),
        critical_gaps_count=critical_count,
        moderate_gaps_count=moderate_count,
        mastered_count=mastered_count,
        overall_accuracy_pct=overall_acc,
        topics=gaps,
    )
