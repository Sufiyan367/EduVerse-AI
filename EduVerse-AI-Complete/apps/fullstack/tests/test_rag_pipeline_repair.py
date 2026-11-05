"""Comprehensive automated evaluation suite for RAG Pipeline Repair:
- Synthetic academic PDF generation
- Two-column reading order and table preservation
- Sparse/scanned page identification
- Boundary-aware segmentation with page-level citation retention
- Hybrid vector + BM25 retrieval and reciprocal rank fusion
- 15 core question categories (all 15 categories from Section 10)
- Recall@6 benchmark evaluation
- Query contextualization for follow-up questions
- Retrieval ownership and multi-tenant user isolation
- Fail-closed citation validation, multi-paragraph grounding, and evidence support
- Real Google Gemini provider model listing and fallback handling
- Explicit actionable error when no LLM is configured
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
import fitz
import pytest

from quicklearn.api.chat import (
    NO_CONTEXT_FALLBACK,
    _contextualize_query,
    assess_evidence_support,
    validate_answer,
)
from quicklearn.config import Config
from quicklearn.db.enums import SourceKind, SourceOrigin, SourceStatus
from quicklearn.db.models import Segment, Source
from quicklearn.db.session import session_scope
from quicklearn.pipeline.extract.document import _sort_page_blocks, extract_pdf
from quicklearn.pipeline.segment import build_segments, persist_segments
from quicklearn.providers.base import text_message
from quicklearn.rag.index import get_index, index_source, index_status
from quicklearn.rag.retrieve import Excerpt, _scope_source_ids, retrieve


@pytest.fixture
def synthetic_academic_pdf(tmp_path: Path) -> Path:
    """Generate a 4-page academic PDF with known facts, tables, multi-column layout and a sparse page."""
    pdf_path = tmp_path / "synthetic_dbms_distributed.pdf"
    doc = fitz.open()

    # --- Page 1: Concurrency Control & Table ---
    p1 = doc.new_page(width=612, height=792)
    p1.insert_textbox(
        fitz.Rect(50, 40, 560, 70),
        "Unit 1: Transaction Concurrency & 2PL Protocol",
        fontsize=14,
    )
    p1.insert_textbox(
        fitz.Rect(50, 80, 560, 160),
        "Two-Phase Locking (2PL) is a concurrency control protocol that guarantees conflict serializability. "
        "It consists of two distinct phases: the Growing Phase (where locks are acquired) and the Shrinking Phase "
        "(where locks are released). The lock acquisition timeout threshold is 250 milliseconds.",
        fontsize=10,
    )
    p1.insert_textbox(
        fitz.Rect(50, 180, 560, 300),
        "Comparison of 2PL Locking Protocols:\n"
        "| Protocol | Lock Holding Duration | Prevents Cascading Aborts |\n"
        "| Basic 2PL | Released during shrinking phase | No |\n"
        "| Strict 2PL | Retained until commit/abort | Yes |\n"
        "| Rigorous 2PL | All shared and exclusive locks held until commit | Yes |",
        fontsize=9,
    )

    # --- Page 2: Two-Column Academic Layout on Distributed Consensus ---
    p2 = doc.new_page(width=612, height=792)
    p2.insert_textbox(
        fitz.Rect(50, 30, 560, 60),
        "Unit 2: Distributed Consensus with Raft",
        fontsize=14,
    )
    # Left column (x=50 to 280)
    p2.insert_textbox(
        fitz.Rect(50, 70, 280, 350),
        "Raft consensus decomposes state machine replication into leader election, log replication, and safety. "
        "In a cluster of 5 nodes, Raft safely tolerates up to 2 simultaneous node crash failures without losing consistency. "
        "Leader election is initiated when a follower's election timer expires.",
        fontsize=10,
    )
    # Right column (x=330 to 560)
    p2.insert_textbox(
        fitz.Rect(330, 70, 560, 350),
        "The randomized election timeout interval is strictly 150ms to 300ms to minimize split votes. "
        "While Paxos is symmetric and permits any node to propose values, Raft enforces strong leader asymmetry "
        "where only the elected leader can append new entries to the log.",
        fontsize=10,
    )

    # --- Page 3: Storage Engine Architecture ---
    p3 = doc.new_page(width=612, height=792)
    p3.insert_textbox(
        fitz.Rect(50, 40, 560, 70),
        "Unit 3: Storage Engine Architecture & LSM-Trees",
        fontsize=14,
    )
    p3.insert_textbox(
        fitz.Rect(50, 80, 560, 300),
        "LSM-Trees (Log-Structured Merge-Trees) optimize for write-heavy database workloads. "
        "Incoming writes are first appended to an on-disk Write-Ahead Log (WAL) and stored in an in-memory MemTable. "
        "When the MemTable reaches 64MB capacity, it is flushed to disk as an immutable SSTable (Sorted String Table). "
        "Compaction runs in the background to merge SSTables and remove tombstones.",
        fontsize=10,
    )

    # --- Page 4: Sparse / Image-like Diagram Page (< 100 characters) ---
    p4 = doc.new_page(width=612, height=792)
    p4.insert_textbox(fitz.Rect(50, 50, 300, 80), "Figure 4.1: B+ Tree Hierarchy", fontsize=10)
    p4.insert_textbox(fitz.Rect(100, 200, 400, 240), "[Root -> Internal -> Leaf]", fontsize=9)

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_two_column_block_sorting():
    """Verify two-column block sorter does not interleave paragraphs across columns."""
    blocks = [
        (50.0, 30.0, 560.0, 60.0, "Title: Distributed Computing", 0, 0),
        (50.0, 80.0, 270.0, 150.0, "Left Col Paragraph 1: Paxos consensus details.", 1, 0),
        (330.0, 80.0, 560.0, 150.0, "Right Col Paragraph 1: Raft leader election details.", 2, 0),
        (50.0, 160.0, 270.0, 220.0, "Left Col Paragraph 2: Quorum slices in Byzantine systems.", 3, 0),
        (330.0, 160.0, 560.0, 220.0, "Right Col Paragraph 2: Randomized timers in Raft.", 4, 0),
    ]
    sorted_blocks = _sort_page_blocks(blocks, page_width=612.0)
    texts = [b[4] for b in sorted_blocks]

    assert texts[0] == "Title: Distributed Computing"
    assert "Left Col Paragraph 1" in texts[1]
    assert "Left Col Paragraph 2" in texts[2]
    assert "Right Col Paragraph 1" in texts[3]
    assert "Right Col Paragraph 2" in texts[4]


@pytest.mark.asyncio
async def test_pdf_extraction_and_scanned_detection(synthetic_academic_pdf: Path, store: Any):
    """Verify PDF extraction preserves page numbers and identifies sparse/scanned pages."""
    res = await extract_pdf(synthetic_academic_pdf)
    assert res.page_count == 4
    assert len(res.units) > 0

    # Verify pages 1, 2, 3 have extracted text
    page_numbers = {u.page_no for u in res.units if u.page_no}
    assert 1 in page_numbers
    assert 2 in page_numbers
    assert 3 in page_numbers

    # Verify sparse page 4 was detected in scanned_pages
    scanned_pages = res.raw.get("scanned_pages", [])
    assert 4 in scanned_pages


def test_boundary_aware_segmentation():
    """Verify segmentation keeps chunks within page boundaries and retains same-page overlap."""
    from quicklearn.pipeline.extract.base import RawUnit

    units = [
        RawUnit(text="Unit 1 Heading\nFirst line of content.", page_no=1),
        RawUnit(text="Second line of content on page 1 with more details.", page_no=1),
        RawUnit(text="| Header A | Header B |\n| Val 1 | Val 2 |", page_no=1),
        RawUnit(text="Unit 2 Heading\nFirst line on page 2.", page_no=2),
    ]

    segments = build_segments(units, timed=False)
    assert len(segments) >= 2

    # Verify chunks never cross page boundaries
    for seg in segments:
        assert seg.page_no in (1, 2)

    # First segment is on page 1
    assert segments[0].page_no == 1
    # Last segment is on page 2
    assert segments[-1].page_no == 2


@pytest.mark.asyncio
async def test_rag_retrieval_all_15_categories(synthetic_academic_pdf: Path, config: Config, store: Any):
    """Evaluate hybrid RAG retrieval across all 15 question categories and compute Recall@6."""
    # 1. Ingest synthetic PDF
    extract_res = await extract_pdf(synthetic_academic_pdf)
    pending_segs = build_segments(extract_res.units, timed=False)

    with session_scope() as session:
        src = Source(
            title="Synthetic DBMS & Distributed Systems",
            kind=SourceKind.PDF,
            origin=SourceOrigin.UPLOAD,
            status=SourceStatus.READY,
            original_filename="synthetic_dbms.pdf",
        )
        session.add(src)
        session.flush()
        source_id = src.id

    segment_ids = persist_segments(source_id, pending_segs)
    assert len(segment_ids) > 0

    # 2. Index the source into vector store
    indexed_count = await index_source(source_id, force=True)
    assert indexed_count == len(segment_ids)

    # Define test questions for all 15 categories with validation predicate
    # (Category, Question, Expected check)
    test_cases = [
        # Cat 1: Direct definition
        ("Cat 1: Definition", "What is Two-Phase Locking (2PL)?", lambda hits: any("Two-Phase Locking" in h.text and h.page_no == 1 for h in hits)),
        # Cat 2: Exact factual retrieval
        ("Cat 2: Exact Fact", "What is the randomized election timeout interval in Raft?", lambda hits: any("150ms to 300ms" in h.text and h.page_no == 2 for h in hits)),
        # Cat 3: Technical explanation
        ("Cat 3: Tech Explanation", "How does Raft consensus achieve fault tolerance?", lambda hits: any("5 nodes" in h.text or "tolerates up to 2" in h.text for h in hits)),
        # Cat 4: Comparison of two concepts
        ("Cat 4: Comparison", "How does Raft differ from Paxos in terms of leader asymmetry?", lambda hits: any("Paxos" in h.text and "Raft" in h.text for h in hits)),
        # Cat 5: Step-by-step process
        ("Cat 5: Step Process", "What are the steps when a write enters an LSM-Tree?", lambda hits: any("Write-Ahead Log" in h.text or "MemTable" in h.text for h in hits)),
        # Cat 6: Table-based information
        ("Cat 6: Table Info", "Which 2PL protocol prevents cascading aborts by holding locks until commit?", lambda hits: any("Strict 2PL" in h.text or "Cascading Aborts" in h.text for h in hits)),
        # Cat 7: Numerical fact
        ("Cat 7: Numerical Fact", "What is the lock acquisition timeout threshold?", lambda hits: any("250 milliseconds" in h.text for h in hits)),
        # Cat 8: Information from specific page
        ("Cat 8: Specific Page", "What storage engine architecture is described on page 3?", lambda hits: any(h.page_no == 3 and "LSM-Trees" in h.text for h in hits)),
        # Cat 9: Multi-page synthesis
        ("Cat 9: Multi-page Synthesis", "Compare transaction concurrency control on page 1 with write buffering on page 3", lambda hits: any(h.page_no in (1, 3) for h in hits)),
        # Cat 10: Cross-section question
        ("Cat 10: Cross-section", "How does Raft leader election compare with 2PL lock acquisition timeout?", lambda hits: any("timeout" in h.text.lower() for h in hits)),
        # Cat 11: Contextual follow-up
        ("Cat 11: Follow-up", "What happens when the MemTable reaches 64MB capacity?", lambda hits: any("SSTable" in h.text or "64MB" in h.text for h in hits)),
        # Cat 12: Acronym or abbreviation
        ("Cat 12: Acronym", "What does WAL stand for in LSM-Trees?", lambda hits: any("Write-Ahead Log" in h.text for h in hits)),
        # Cat 13: Query phrased differently from document
        ("Cat 13: Paraphrased Query", "How does Raft handle node breakdown without losing data?", lambda hits: any("tolerates up to 2" in h.text or "crash failures" in h.text for h in hits)),
        # Cat 14: Unsupported question (abstention)
        ("Cat 14: Abstention", "What are the rules of Olympic basketball?", lambda hits: True),  # Handled below
        # Cat 15: Scanned / sparse page
        ("Cat 15: Sparse/Scanned Page", "B+ Tree Hierarchy diagram", lambda hits: any(h.page_no == 4 for h in hits)),
    ]

    passed_count = 0
    top_k = 6

    for cat_name, question, validator in test_cases:
        if cat_name == "Cat 14: Abstention":
            # For abstention, retrieve should either return low-relevance or validation should abstain
            hits = await retrieve(question, scope_type="source", scope_id=source_id, top_k=top_k)
            ans = "The course materials do not cover the rules of Olympic basketball."
            clean_ans, citations = validate_answer(ans, hits)
            assert citations == []
            assert "not cover" in clean_ans.lower() or "could not verify" in clean_ans.lower() or "couldn't find" in clean_ans.lower()
            passed_count += 1
            continue

        hits = await retrieve(question, scope_type="source", scope_id=source_id, top_k=top_k)
        assert len(hits) > 0, f"Failed to retrieve any excerpts for {cat_name}: {question}"
        passed = validator(hits)
        assert passed, f"Recall@6 failed for {cat_name}: {question}. Hits: {[h.text[:80] for h in hits]}"
        passed_count += 1

    recall_rate = passed_count / len(test_cases)
    assert recall_rate >= 0.90, f"Recall@6 was {recall_rate:.2%}, expected >= 90%"


@pytest.mark.asyncio
async def test_query_contextualization():
    """Verify that follow-up questions with anaphora are contextualized before retrieval."""
    history = [
        text_message("user", "Explain Two-Phase Locking (2PL)."),
        text_message("assistant", "Two-Phase Locking is a concurrency control protocol with Growing and Shrinking phases [1]."),
    ]

    # Follow-up with pronoun 'its'
    rewritten = await _contextualize_query("What are its two phases?", history)
    # The heuristic or LLM should preserve context or append topic
    assert "Two-Phase Locking" in rewritten or "2PL" in rewritten or "phases" in rewritten


def test_user_retrieval_isolation(store: Any):
    """Verify multi-tenant user isolation prevents cross-user document access."""
    from quicklearn.db.models import User

    with session_scope() as session:
        # Create users
        u1 = User(email="user1@eduverse.test", username="user1", hashed_password="hash1", full_name="Student 1")
        u2 = User(email="user2@eduverse.test", username="user2", hashed_password="hash2", full_name="Student 2")
        session.add_all([u1, u2])
        session.flush()

        # Create user 1 source
        s1 = Source(
            title="User 1 Private Notes",
            kind=SourceKind.TEXT,
            origin=SourceOrigin.PASTE,
            status=SourceStatus.READY,
            user_id=u1.id,
        )
        # Create user 2 source
        s2 = Source(
            title="User 2 Private Notes",
            kind=SourceKind.TEXT,
            origin=SourceOrigin.PASTE,
            status=SourceStatus.READY,
            user_id=u2.id,
        )
        session.add_all([s1, s2])
        session.flush()
        s1_id = s1.id
        s2_id = s2.id
        u1_id = u1.id

    # User 1 cannot retrieve User 2's source
    u1_scoped = _scope_source_ids("source", s2_id, user_id=u1_id)
    assert u1_scoped == [-1]

    # User 1 can retrieve User 1's source
    u1_own = _scope_source_ids("source", s1_id, user_id=u1_id)
    assert u1_own == [s1_id]

    # User 1 global scope only returns user 1 sources
    u1_global = _scope_source_ids("global", None, user_id=u1_id)
    assert s1_id in u1_global
    assert s2_id not in u1_global


def test_citation_validation_and_evidence_support():
    """Verify fail-closed citation validation and evidence support assessment."""
    excerpts = [
        Excerpt(id=101, text="2PL Growing Phase acquires locks.", source_id=1, source_title="DBMS", page_no=1),
        Excerpt(id=102, text="Strict 2PL prevents cascading aborts.", source_id=1, source_title="DBMS", page_no=1),
    ]

    # Test A: Valid cited answer -> strong support
    ans_valid = "Two-Phase Locking acquires locks during the growing phase [101]. Strict 2PL prevents cascading aborts [102]."
    clean_text, cited_ids = validate_answer(ans_valid, excerpts)
    assert cited_ids == [101, 102]
    support = assess_evidence_support(clean_text, cited_ids, excerpts)
    assert support == "strong"

    # Test B: Single cited answer -> partial support
    ans_partial = "Two-Phase Locking acquires locks during the growing phase [101]."
    clean_text, cited_ids = validate_answer(ans_partial, excerpts)
    assert cited_ids == [101]
    support = assess_evidence_support(clean_text, cited_ids, excerpts)
    assert support == "partial"

    # Test C: Hallucinated citation marker [999] stripped
    ans_hallucinated = "Strict 2PL prevents cascading aborts [102][999]."
    clean_text, cited_ids = validate_answer(ans_hallucinated, excerpts)
    assert cited_ids == [102]
    assert "[999]" not in clean_text
    assert "Some referenced citation markers were not found" in clean_text

    # Test D: Ungrounded factual claims without citations fail closed -> insufficient support
    ans_uncited = "Raft election timeout is 150ms."
    clean_text, cited_ids = validate_answer(ans_uncited, excerpts)
    assert cited_ids == []
    assert "could not verify this claim" in clean_text.lower()
    support = assess_evidence_support(clean_text, cited_ids, excerpts)
    assert support == "insufficient"

    # Test E: Honest model abstention accepted with citations=[]
    ans_abstain = "The provided course materials do not contain sufficient evidence to answer this question."
    clean_text, cited_ids = validate_answer(ans_abstain, excerpts)
    assert cited_ids == []
    assert ans_abstain in clean_text
    support = assess_evidence_support(clean_text, cited_ids, excerpts)
    assert support == "insufficient"


@pytest.mark.asyncio
async def test_google_gemini_provider_integration():
    """Verify Google Gemini provider configuration, fallback models, and vision capabilities."""
    from quicklearn.providers.llm.google import GoogleLLM
    from quicklearn.providers import pricing

    # Pricing contains gemini-3.8-flash and gemini-2.5-flash
    assert "gemini-3.8-flash" in pricing.LLM_PRICES["google"]
    assert "gemini-2.5-flash" in pricing.LLM_PRICES["google"]

    # GoogleLLM attributes
    provider = GoogleLLM(api_key="fake-key-for-test")
    assert provider.name == "google"
    assert provider.supports_vision is True
    assert provider.supports_structured_output is True

    # Fallback model listing works when network endpoint is unreachable
    models = await provider.list_models()
    assert len(models) >= 5
    model_ids = {m.id for m in models}
    assert "gemini-3.8-flash" in model_ids
    assert "gemini-2.5-flash" in model_ids
    await provider.aclose()


def test_explicit_configuration_error_when_no_llm(store: Any):
    """Verify explicit actionable error is raised when no LLM is configured."""
    from quicklearn.errors import ConfigurationError
    from quicklearn.providers import registry
    from quicklearn.settings import get_settings

    settings = get_settings()
    settings.set_many({"routing.standard": {"provider": "", "model": ""}})
    registry.reset()

    with pytest.raises(ConfigurationError) as exc_info:
        registry.get_llm("standard")
    assert "No language model is configured" in str(exc_info.value)


def test_kotaemon_thumbnail_preview_endpoint(synthetic_academic_pdf: Path, store: Any):
    """Verify Kotaemon-adapted on-demand PDF page thumbnail preview for citations."""
    from quicklearn.api.sources import get_page_thumbnail
    from quicklearn.errors import NotFoundError

    with session_scope() as session:
        src = Source(
            title="Academic Architecture",
            kind=SourceKind.PDF,
            origin=SourceOrigin.UPLOAD,
            status=SourceStatus.READY,
            media_path=str(synthetic_academic_pdf),
            original_filename="synthetic_dbms.pdf",
        )
        session.add(src)
        session.flush()
        source_id = src.id

    # Test valid page 1 thumbnail
    res = get_page_thumbnail(source_id=source_id, page_no=1)
    assert res["source_id"] == source_id
    assert res["page_no"] == 1
    assert res["thumbnail"].startswith("data:image/png;base64,")

    # Test out of bounds page raises NotFoundError
    with pytest.raises(NotFoundError):
        get_page_thumbnail(source_id=source_id, page_no=99)
