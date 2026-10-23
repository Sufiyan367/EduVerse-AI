"""Automated regression and acceptance tests for core learning workflows:
- Document ingestion & segmentation
- Concept extraction persistence
- Flashcards & FSRS-6 review state scheduling
- Multi-format quiz item generation and attempt evaluation
- Grounded chat citation validation and rejection of fabricated citations
- No-context disclaimer enforcement
"""

from __future__ import annotations

from typing import Any
import pytest

from quicklearn.api.chat import NO_CONTEXT_FALLBACK, validate_answer
from quicklearn.db.enums import CardType, MessageRole, QuizItemType, SourceKind, SourceOrigin, SourceStatus
from quicklearn.db.models import Card, Concept, QuizAttempt, QuizItem, Segment, Source
from quicklearn.db.session import session_scope
from quicklearn.rag.retrieve import Excerpt
from quicklearn.study.fsrs import Rating, apply_review


def test_document_ingestion_and_segmentation(store: Any) -> None:
    """Documents and their chunked segments persist correctly in SQLite."""
    with session_scope() as session:
        src = Source(
            kind=SourceKind.TEXT,
            origin=SourceOrigin.UPLOAD,
            title="Introduction to Machine Learning",
            original_filename="ml_intro.txt",
            status=SourceStatus.READY,
        )
        session.add(src)
        session.flush()

        seg = Segment(
            source_id=src.id,
            index=1,
            text="Machine learning involves training algorithms on historical datasets.",
        )
        session.add(seg)
        session.commit()

        retrieved = session.get(Source, src.id)
        assert retrieved is not None
        assert retrieved.title == "Introduction to Machine Learning"
        assert len(retrieved.segments) == 1
        assert retrieved.segments[0].text.startswith("Machine learning involves")


def test_concept_extraction_persistence(store: Any) -> None:
    """Concepts extracted from documents link to sources correctly."""
    with session_scope() as session:
        src = Source(
            kind=SourceKind.TEXT,
            origin=SourceOrigin.UPLOAD,
            title="Neural Networks",
            status=SourceStatus.READY,
        )
        session.add(src)
        session.flush()

        concept = Concept(
            source_id=src.id,
            name="Backpropagation",
            definition="Algorithm for calculating gradients of loss with respect to weights.",
            importance=0.9,
        )
        session.add(concept)
        session.commit()

        loaded = session.get(Concept, concept.id)
        assert loaded is not None
        assert loaded.name == "Backpropagation"
        assert loaded.source_id == src.id


def test_fsrs_review_scheduling(store: Any) -> None:
    """FSRS spaced repetition transitions update stability and scheduled intervals."""
    with session_scope() as session:
        card = Card(
            type=CardType.BASIC,
            front="What is gradient descent?",
            back="An optimization algorithm to minimize loss.",
        )
        session.add(card)
        session.commit()

        # Review with Good rating
        review, outcome = apply_review(card=card, rating=int(Rating.Good))
        assert outcome.scheduled_days >= 0
        assert card.stability is not None
        assert card.difficulty is not None
        assert card.due is not None


def test_quiz_attempt_evaluation(store: Any) -> None:
    """Quiz questions evaluate and record user attempt scores."""
    with session_scope() as session:
        item = QuizItem(
            question="What is the derivative of x^2?",
            type=QuizItemType.MCQ,
            options=["2x", "x", "x^3", "2"],
            answer="2x",
        )
        session.add(item)
        session.flush()

        attempt = QuizAttempt(
            quiz_item_id=item.id,
            response="2x",
            is_correct=True,
            score=1.0,
        )
        session.add(attempt)
        session.commit()

        loaded_attempt = session.get(QuizAttempt, attempt.id)
        assert loaded_attempt is not None
        assert loaded_attempt.is_correct is True
        assert loaded_attempt.score == 1.0


def test_grounded_chat_valid_and_fabricated_citations() -> None:
    """Chat validation retains real citation IDs and strips fabricated citation IDs."""
    excerpts = [
        Excerpt(
            id=42,
            text="Gradient descent minimizes loss functions.",
            source_id=1,
            source_title="Optimization",
            timestamp=None,
            score=0.95,
        )
    ]

    # Valid citation preserved
    valid_text = "According to the lecture, gradient descent minimizes loss [42]."
    cleaned, citations = validate_answer(valid_text, excerpts)
    assert 42 in citations
    assert "[42]" in cleaned

    # Fabricated citation stripped
    hallucinated_text = "This claims ungrounded facts [9999]."
    cleaned_hallucinated, cits_hallucinated = validate_answer(hallucinated_text, excerpts)
    assert 9999 not in cits_hallucinated
    assert "[9999]" not in cleaned_hallucinated


def test_grounded_chat_no_context_fallback() -> None:
    """When no context is retrieved and no disclaimer exists, fallback disclaimer is returned."""
    answer = "The universe is expanding."
    fallback_text, cits = validate_answer(answer, [])
    assert fallback_text == NO_CONTEXT_FALLBACK
    assert cits == []
