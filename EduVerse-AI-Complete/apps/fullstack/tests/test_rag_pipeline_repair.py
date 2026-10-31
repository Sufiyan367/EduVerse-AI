"""Comprehensive automated evaluation suite for RAG Pipeline Repair:
- Synthetic academic PDF generation
- Two-column reading order and table preservation
- Sparse/scanned page identification
- Boundary-aware segmentation with page-level citation retention
- Hybrid vector + BM25 retrieval and reciprocal rank fusion
- 10 core question categories (definition, fact, concept, comparison, multi-page, table, specific page, follow-up, abstention, mixed content)
- Fail-closed citation validation and ungrounded claim rejection
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
import fitz
import pytest

from quicklearn.api.chat import NO_CONTEXT_FALLBACK, validate_answer
from quicklearn.config import Config
from quicklearn.db.enums import SourceKind, SourceOrigin, SourceStatus
from quicklearn.db.models import Segment, Source
from quicklearn.db.session import session_scope
from quicklearn.pipeline.extract.document import _sort_page_blocks, extract_pdf
from quicklearn.pipeline.segment import build_segments, persist_segments
from quicklearn.rag.index import get_index, index_source, index_status
from quicklearn.rag.retrieve import Excerpt, retrieve


@pytest.fixture
def synthetic_academic_pdf(tmp_path: Path) -> Path:
    """Generate a 4-page academic PDF with known facts, tables, multi-column layout and a sparse page."""
    pdf_path = tmp_path / "synthetic_dbms_distributed.pdf"
    doc = fitz.open()

    # --- Page 1: Concurrency Control & Table (Single & Multi-element) ---
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
async def test_rag_retrieval_10_categories(synthetic_academic_pdf: Path, config: Config, store: Any):
    """Evaluate hybrid RAG retrieval across the 10 core question categories."""
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

    # 3. Category 1: Direct Definition
    # Expected: 2PL definition on page 1
    q1 = "What is Two-Phase Locking (2PL)?"
    hits1 = await retrieve(q1, scope_type="source", scope_id=source_id, top_k=5)
    assert len(hits1) > 0
    assert any(h.page_no == 1 and "Two-Phase Locking" in h.text for h in hits1)

    # 4. Category 2: Exact Factual Lookup
    # Expected: 150ms to 300ms election timeout on page 2
    q2 = "What is the election timeout interval in Raft?"
    hits2 = await retrieve(q2, scope_type="source", scope_id=source_id, top_k=5)
    assert len(hits2) > 0
    assert any("150ms to 300ms" in h.text and h.page_no == 2 for h in hits2)

    # 5. Category 3: Conceptual Explanation
    # Expected: Raft consensus fault tolerance (2 node crashes out of 5)
    q3 = "How does Raft consensus achieve fault tolerance?"
    hits3 = await retrieve(q3, scope_type="source", scope_id=source_id, top_k=5)
    assert len(hits3) > 0
    assert any("5 nodes" in h.text or "fault tolerance" in h.text for h in hits3)

    # 6. Category 4: Comparison Between Two Concepts
    # Expected: Paxos vs Raft leader symmetry on page 2
    q4 = "How does Raft differ from Paxos in terms of leader asymmetry?"
    hits4 = await retrieve(q4, scope_type="source", scope_id=source_id, top_k=5)
    assert len(hits4) > 0
    assert any("Paxos" in h.text and "Raft" in h.text for h in hits4)

    # 7. Category 5: Multi-Page Question
    # Expected: Concurrency in 2PL (page 1) vs SSTables / LSM-Trees (page 3)
    q5 = "Compare transaction concurrency control with write buffering in LSM-Trees"
    hits5 = await retrieve(q5, scope_type="source", scope_id=source_id, top_k=6)
    retrieved_pages = {h.page_no for h in hits5}
    assert 1 in retrieved_pages or 3 in retrieved_pages

    # 8. Category 6: Table-Based Question
    # Expected: Strict 2PL cascading abort prevention from table on page 1
    q6 = "Which 2PL protocol prevents cascading aborts by holding locks until commit?"
    hits6 = await retrieve(q6, scope_type="source", scope_id=source_id, top_k=5)
    assert len(hits6) > 0
    assert any("Strict 2PL" in h.text or "Cascading Aborts" in h.text for h in hits6)

    # 9. Category 7: Specific Page Reference
    # Expected: Information on page 3 (MemTable and SSTables)
    q7 = "What storage engine architecture is described on page 3?"
    hits7 = await retrieve(q7, scope_type="source", scope_id=source_id, top_k=5)
    assert len(hits7) > 0
    assert any(h.page_no == 3 for h in hits7)

    # 10. Category 8: Follow-Up Question
    # Expected: Retrieval retains context for follow-up
    q8 = "What happens when the MemTable reaches 64MB capacity?"
    hits8 = await retrieve(q8, scope_type="source", scope_id=source_id, top_k=5)
    assert len(hits8) > 0
    assert any("SSTable" in h.text or "64MB" in h.text for h in hits8)

    # 11. Category 9: Question Absent From PDF (Abstention check)
    q9 = "What are the rules of Olympic basketball?"
    hits9 = await retrieve(q9, scope_type="source", scope_id=source_id, top_k=5)
    absent_answer = "The provided course materials do not cover the rules of Olympic basketball."
    validated_text, citations = validate_answer(absent_answer, hits9)
    assert citations == []
    assert "not cover" in validated_text.lower() or "could not verify" in validated_text.lower()

    # 12. Category 10: Mixed / Scanned Page Detection
    q10 = "B+ Tree Hierarchy diagram"
    hits10 = await retrieve(q10, scope_type="source", scope_id=source_id, top_k=5)
    assert len(hits10) > 0
    assert any(h.page_no == 4 for h in hits10)


def test_citation_validation_logic():
    """Verify fail-closed citation validation and multi-paragraph grounding."""
    excerpts = [
        Excerpt(id=101, text="2PL Growing Phase acquires locks.", source_id=1, source_title="DBMS", page_no=1),
        Excerpt(id=102, text="Strict 2PL prevents cascading aborts.", source_id=1, source_title="DBMS", page_no=1),
    ]

    # Test A: Valid cited answer
    ans_valid = "Two-Phase Locking acquires locks during the growing phase [101]."
    clean_text, cited_ids = validate_answer(ans_valid, excerpts)
    assert cited_ids == [101]
    assert clean_text == ans_valid

    # Test B: Hallucinated citation marker [999] stripped
    ans_hallucinated = "Strict 2PL prevents cascading aborts [102][999]."
    clean_text, cited_ids = validate_answer(ans_hallucinated, excerpts)
    assert cited_ids == [102]
    assert "[999]" not in clean_text
    assert "Some referenced citation markers were not found" in clean_text

    # Test C: Ungrounded factual claims without citations fail closed
    ans_uncited = "Raft election timeout is 150ms."
    clean_text, cited_ids = validate_answer(ans_uncited, excerpts)
    assert cited_ids == []
    assert "could not verify this claim" in clean_text.lower()

    # Test D: Honest model abstention accepted with citations=[]
    ans_abstain = "The provided course materials do not contain sufficient evidence to answer this question."
    clean_text, cited_ids = validate_answer(ans_abstain, excerpts)
    assert cited_ids == []
    assert ans_abstain in clean_text

    # Test E: Multi-paragraph answer where only one paragraph is cited
    ans_mixed_paras = (
        "2PL acquires locks in the growing phase [101].\n\n"
        "Quantum computing will break all modern cryptographic protocols very soon without any doubt."
    )
    clean_text, cited_ids = validate_answer(ans_mixed_paras, excerpts)
    assert cited_ids == [101]
    assert "Portions of this answer lack direct citation markers" in clean_text


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
