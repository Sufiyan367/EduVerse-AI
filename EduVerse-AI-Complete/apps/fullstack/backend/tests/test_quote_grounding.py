"""Unit tests for Quote Normalization and Evidence Verification."""

import pytest
from quicklearn.rag.grounding import (
    find_evidence_span,
    normalize_for_matching,
    normalized_with_map,
    verify_evidence_in_segments,
)


def test_line_break_hyphenation_and_wrapped_words():
    # Document text with hyphenated wrap
    text = "Modern database systems ensure concur-\nrency control using multi-version schemes."
    quote = "concurrency control using multi-version schemes"

    norm_text = normalize_for_matching(text)
    norm_quote = normalize_for_matching(quote)
    assert norm_quote in norm_text

    span = find_evidence_span(text, quote)
    assert span is not None
    start, end = span
    matched_orig = text[start:end]
    # The original span contains the hyphen and newline intact!
    assert "concur-\nrency" in matched_orig


def test_margin_numbers_stripped_without_damaging_numbered_lists_and_equations():
    doc_text = (
        "12\n"  # isolated margin number
        "1. Overview of Distributed Transactions\n"
        "Distributed transactions must satisfy ACID properties.\n"
        "34\n"  # isolated margin number
        "The formula for throughput is T = 2 * N + 1 where N >= 1.\n"
        "Section 4.2 details the protocol."
    )

    # 1. Margin numbers are stripped in matching representation
    norm = normalize_for_matching(doc_text)
    assert "12" not in norm.split()[:2]
    assert "34" not in norm.split()

    # 2. Numbered lists are preserved
    assert "1. overview" in norm

    # 3. Equations are preserved
    assert "t = 2 * n + 1" in norm

    # 4. Section references are preserved
    assert "section 4.2" in norm

    # Quote verification
    span_list = find_evidence_span(doc_text, "1. Overview of Distributed Transactions")
    assert span_list is not None
    assert doc_text[span_list[0]:span_list[1]] == "1. Overview of Distributed Transactions"

    span_eq = find_evidence_span(doc_text, "T = 2 * N + 1")
    assert span_eq is not None
    assert doc_text[span_eq[0]:span_eq[1]] == "T = 2 * N + 1"


def test_ligatures_and_unicode_inconsistencies():
    # Text with typographical ligature (fi -> ﬁ), smart quotes, and em-dash
    text = "The speciﬁc “two-phase commit” protocol—used across nodes—guarantees atomicity."
    # Standard quote without ligatures and standard ASCII quotes/hyphens
    quote = 'specific "two-phase commit" protocol-used across nodes-guarantees atomicity'

    norm_text = normalize_for_matching(text)
    norm_quote = normalize_for_matching(quote)

    assert "specific" in norm_text
    assert norm_quote in norm_text

    span = find_evidence_span(text, "specific “two-phase commit”")
    assert span is not None


def test_verify_evidence_in_segments_positive_and_negative():
    mock_segments = [
        {
            "id": 101,
            "source_id": 1,
            "page_no": 3,
            "text": "Strict two-phase locking (S2PL) prevents cascading rollbacks.",
        },
        {
            "id": 102,
            "source_id": 1,
            "page_no": 4,
            "text": "Deadlocks can be detected using a wait-for graph cycle check.",
        },
    ]

    # Positive test
    match_pos = verify_evidence_in_segments(
        "Strict two-phase locking (S2PL) prevents cascading rollbacks",
        mock_segments,
    )
    assert match_pos.matched is True
    assert match_pos.segment_id == 101
    assert match_pos.source_id == 1
    assert match_pos.page_no == 3
    assert match_pos.confidence == 1.0
    assert match_pos.matched_span is not None

    # Negative test (hallucinated quote)
    match_neg = verify_evidence_in_segments(
        "PostgreSQL 17 was released in 1985 by Satoshi Nakamoto.",
        mock_segments,
    )
    assert match_neg.matched is False
    assert match_neg.segment_id is None
    assert match_neg.confidence == 0.0


def test_cross_segment_boundary_matching():
    mock_segments = [
        {
            "id": 201,
            "source_id": 5,
            "page_no": 1,
            "text": "Linearizability guarantees that every operation appears to take effect",
        },
        {
            "id": 202,
            "source_id": 5,
            "page_no": 1,
            "text": "instantaneously at some point between its invocation and completion.",
        },
    ]

    quote = "every operation appears to take effect instantaneously at some point"
    match = verify_evidence_in_segments(quote, mock_segments)
    assert match.matched is True
    assert match.segment_id == 201
    assert match.source_id == 5
    assert match.confidence >= 0.95
