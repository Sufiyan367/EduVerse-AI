"""Knowledge Gap API endpoints for EduVerse AI."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..study.knowledge_gap import analyze_knowledge_gaps

router = APIRouter(prefix="/knowledge-gap", tags=["knowledge-gap"])


class EvidenceOut(BaseModel):
    question: str
    user_answer: str
    correct_answer: str
    explanation: str


class TopicGapOut(BaseModel):
    topic_id: int | None
    topic_name: str
    source_id: int | None
    source_title: str | None
    definition: str
    total_questions: int
    correct_questions: int
    accuracy_pct: float
    status: str
    evidence: list[EvidenceOut]


class KnowledgeGapSummaryOut(BaseModel):
    total_evaluated_topics: int
    critical_gaps_count: int
    moderate_gaps_count: int
    mastered_count: int
    overall_accuracy_pct: float
    topics: list[TopicGapOut]


@router.get("/summary", response_model=KnowledgeGapSummaryOut)
def get_knowledge_gap_summary(db: Session = Depends(get_db)) -> KnowledgeGapSummaryOut:
    """Analyze all quiz attempts and return knowledge gap overview."""
    summary = analyze_knowledge_gaps(db)
    return KnowledgeGapSummaryOut(
        total_evaluated_topics=summary.total_evaluated_topics,
        critical_gaps_count=summary.critical_gaps_count,
        moderate_gaps_count=summary.moderate_gaps_count,
        mastered_count=summary.mastered_count,
        overall_accuracy_pct=summary.overall_accuracy_pct,
        topics=[
            TopicGapOut(
                topic_id=t.topic_id,
                topic_name=t.topic_name,
                source_id=t.source_id,
                source_title=t.source_title,
                definition=t.definition,
                total_questions=t.total_questions,
                correct_questions=t.correct_questions,
                accuracy_pct=t.accuracy_pct,
                status=t.status,
                evidence=[
                    EvidenceOut(
                        question=e.question,
                        user_answer=e.user_answer,
                        correct_answer=e.correct_answer,
                        explanation=e.explanation,
                    )
                    for e in t.evidence
                ],
            )
            for t in summary.topics
        ],
    )


@router.get("/topics", response_model=list[TopicGapOut])
def get_knowledge_gap_topics(db: Session = Depends(get_db)) -> list[TopicGapOut]:
    """Return all assessed topics sorted by urgency."""
    summary = analyze_knowledge_gaps(db)
    return [
        TopicGapOut(
            topic_id=t.topic_id,
            topic_name=t.topic_name,
            source_id=t.source_id,
            source_title=t.source_title,
            definition=t.definition,
            total_questions=t.total_questions,
            correct_questions=t.correct_questions,
            accuracy_pct=t.accuracy_pct,
            status=t.status,
            evidence=[
                EvidenceOut(
                    question=e.question,
                    user_answer=e.user_answer,
                    correct_answer=e.correct_answer,
                    explanation=e.explanation,
                )
                for e in t.evidence
            ],
        )
        for t in summary.topics
    ]
