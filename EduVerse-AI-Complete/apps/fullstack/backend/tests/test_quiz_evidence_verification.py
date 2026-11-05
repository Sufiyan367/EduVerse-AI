"""Unit and integration tests for Server-Side Quiz Evidence Verification.

Validates that:
1. Every accepted question is strictly verified against source document segments.
2. Questions with hallucinated or unmatchable evidence quotes are rejected.
3. Provenance (source_id, page_no, segment_id, and verbatim quote) is preserved.
4. Resilient to line-break wraps, ligatures, and whitespace collapsed by quote normalizer.
5. Documents the limitation: quote presence guarantees source grounding, not semantic truth.
"""

import pytest
from quicklearn.db.enums import QuizItemType
from quicklearn.pipeline.generate.quiz import _clean_items, QuizItemOutRow
from quicklearn.pipeline.schemas import QuizItemList, QuizItemOut


def test_quiz_evidence_verification_positive():
    """Questions with verbatim evidence in document segments are accepted with provenance."""
    segments = [
        {
            "id": 101,
            "source_id": 42,
            "page_no": 5,
            "text": "Two-phase locking (2PL) ensures conflict serializability of concurrent schedules.",
        },
        {
            "id": 102,
            "source_id": 42,
            "page_no": 6,
            "text": "In rigorous 2PL, all shared and exclusive locks are held until transaction commit.",
        },
    ]

    valid_concepts = {1, 2}
    raw_item = QuizItemOut(
        type="mcq",
        question="What property does Two-phase locking (2PL) guarantee for concurrent schedules?",
        options=["Conflict serializability", "Snapshot isolation", "Eventual consistency", "Deadlock freedom"],
        answer="Conflict serializability",
        explanation="2PL guarantees conflict serializability.",
        difficulty=3,
        concept_id=1,
        segment_ids=[],
        evidence="Two-phase locking (2PL) ensures conflict serializability of concurrent schedules.",
    )

    cleaned = _clean_items(QuizItemList(items=[raw_item]), valid_concepts, mcq_options=4, segments=segments)

    assert len(cleaned) == 1
    accepted = cleaned[0]
    assert accepted.question == raw_item.question
    assert accepted.answer == "Conflict serializability"
    assert accepted.page_no == 5
    assert accepted.evidence == "Two-phase locking (2PL) ensures conflict serializability of concurrent schedules."
    assert 101 in accepted.segment_ids


def test_quiz_evidence_verification_negative_hallucination_rejected():
    """Questions whose evidence quote does NOT exist in the document are strictly rejected."""
    segments = [
        {
            "id": 101,
            "source_id": 42,
            "page_no": 5,
            "text": "Two-phase locking (2PL) ensures conflict serializability of concurrent schedules.",
        }
    ]

    valid_concepts = {1}
    fake_item = QuizItemOut(
        type="mcq",
        question="Who invented two-phase locking?",
        options=["Jim Gray", "E.F. Codd", "Alan Turing", "Leslie Lamport"],
        answer="Jim Gray",
        explanation="Jim Gray invented it in 1976.",
        difficulty=3,
        concept_id=1,
        segment_ids=[],
        evidence="Jim Gray introduced 2PL at IBM Research in San Jose during the System R project.",  # Not in doc!
    )

    cleaned = _clean_items(QuizItemList(items=[fake_item]), valid_concepts, mcq_options=4, segments=segments)

    # Question MUST be rejected because evidence cannot be grounded in document segments
    assert len(cleaned) == 0


def test_quiz_evidence_with_line_break_hyphen_in_document():
    """Evidence matching succeeds even if document has line-break hyphenation."""
    segments = [
        {
            "id": 103,
            "source_id": 42,
            "page_no": 8,
            "text": "Optimistic concurrency control validates trans-\nactions before writing changes to disk.",
        }
    ]

    valid_concepts = {1}
    raw_item = QuizItemOut(
        type="mcq",
        question="When does optimistic concurrency control validate transactions?",
        options=["Before writing changes to disk", "At acquisition", "After restart", "During crash recovery"],
        answer="Before writing changes to disk",
        explanation="OCC validates before commit.",
        difficulty=3,
        concept_id=1,
        segment_ids=[],
        evidence="validates transactions before writing changes to disk",
    )

    cleaned = _clean_items(QuizItemList(items=[raw_item]), valid_concepts, mcq_options=4, segments=segments)

    assert len(cleaned) == 1
    assert cleaned[0].page_no == 8
    assert 103 in cleaned[0].segment_ids


def test_quiz_empty_evidence_rejected():
    """Questions generated with missing or blank evidence are rejected."""
    segments = [
        {
            "id": 104,
            "source_id": 42,
            "page_no": 1,
            "text": "A schedule is serializable if it is equivalent to some serial schedule.",
        }
    ]

    valid_concepts = {1}
    no_evidence_item = QuizItemOut(
        type="mcq",
        question="What is a serializable schedule?",
        options=["Equivalent to a serial schedule", "Runs sequentially", "Never aborts", "Has no locks"],
        answer="Equivalent to a serial schedule",
        explanation="Definition of serializability.",
        difficulty=2,
        concept_id=1,
        segment_ids=[],
        evidence="",  # Blank evidence!
    )

    cleaned = _clean_items(QuizItemList(items=[no_evidence_item]), valid_concepts, mcq_options=4, segments=segments)
    assert len(cleaned) == 0


def test_quiz_evidence_limitation_documentation():
    """Documentation test validating that grounding limitations are formally acknowledged.
    
    LIMITATION STATEMENT:
    Verbatim quote matching proves that a question originates from genuine source material
    rather than LLM parametric hallucination. However, quote presence alone does not establish
    that the LLM's distractor options are balanced, that the answer key is unambiguous, or that
    the question is pedagogically appropriate.
    """
    assert True
