"""Live end-to-end verification of EduVerse PDF intelligence pipeline.

Ingests 3 real curriculum PDFs:
1. EduVerse_AI_Project_Report.pdf (25 pages academic report)
2. EduVerse_AI_Two_Page_Report.pdf (2 pages summary report)
3. Advanced_Database_Concurrency.pdf (synthetic curriculum material with known facts & tables)

Verifies:
- Document extraction fidelity
- Page counts
- Segment persistence
- FTS5 keyword indexing
- Vector indexing (sqlite-vec)
- Local GPU inference via Ollama (qwen3.5:4b)
- Grounded citations [ID] with exact page numbers
- Honest abstention on unsupported questions
- Persistence across simulated backend restart
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import fitz
from quicklearn import prompts
from quicklearn.api.chat import assess_evidence_support, validate_answer
from quicklearn.config import Config, set_config
from quicklearn.db.bootstrap import init_database
from quicklearn.db.enums import SourceKind, SourceOrigin, SourceStatus
from quicklearn.db.models import Segment, Source, Transcript
from quicklearn.db.session import raw_sqlite, session_scope, vec_available
from quicklearn.pipeline import acquire, stages
from quicklearn.providers import gateway
from quicklearn.rag import index as rag_index
from quicklearn.rag import retrieve as rag


def create_curriculum_pdf(destination: Path) -> Path:
    """Generate a high-density academic curriculum PDF with tables and known facts."""
    doc = fitz.open()

    # Page 1: Strict Two-Phase Locking & Serializable Snapshot Isolation
    p1 = doc.new_page(width=612, height=792)
    p1.insert_text((72, 50), "Distributed Transaction Processing: Serializability", fontsize=15)
    p1.insert_textbox(
        fitz.Rect(72, 80, 540, 160),
        "Serializable Snapshot Isolation (SSI) detects rw-antidependencies in the serialization graph "
        "without acquiring shared read locks. In contrast, Strict 2PL requires exclusive write locks "
        "to be held strictly until transaction commit or abort. The maximum lock wait timeout for "
        "distributed 2PC transactions is set to exactly 350 milliseconds.",
        fontsize=10,
    )

    # Draw a table with grid
    p1.draw_rect(fitz.Rect(72, 170, 540, 280))
    p1.draw_line(fitz.Point(72, 200), fitz.Point(540, 200))
    p1.draw_line(fitz.Point(72, 240), fitz.Point(540, 240))
    p1.draw_line(fitz.Point(230, 170), fitz.Point(230, 280))
    p1.draw_line(fitz.Point(380, 170), fitz.Point(380, 280))

    p1.insert_text((80, 190), "Isolation Level", fontsize=9)
    p1.insert_text((240, 190), "Anomaly Prevented", fontsize=9)
    p1.insert_text((390, 190), "Throughput Penalty", fontsize=9)

    p1.insert_text((80, 225), "Read Committed", fontsize=9)
    p1.insert_text((240, 225), "Dirty Reads Only", fontsize=9)
    p1.insert_text((390, 225), "Low (~5%)", fontsize=9)

    p1.insert_text((80, 265), "Serializable (SSI)", fontsize=9)
    p1.insert_text((240, 265), "Write Skew & Phantoms", fontsize=9)
    p1.insert_text((390, 265), "Moderate (~18%)", fontsize=9)

    # Page 2: Raft Joint Consensus
    p2 = doc.new_page(width=612, height=792)
    p2.insert_text((72, 50), "Distributed Consensus: Dynamic Cluster Membership", fontsize=15)
    p2.insert_textbox(
        fitz.Rect(72, 80, 540, 160),
        "Cluster configuration transitions in Raft utilize Joint Consensus (C_old,new). "
        "During joint consensus, configuration entries are committed when accepted by a majority "
        "of the old cluster and a majority of the new cluster simultaneously. "
        "The heartbeat interval for leader leases is fixed at 50 milliseconds.",
        fontsize=10,
    )

    doc.save(str(destination))
    doc.close()
    return destination


async def ingest_document(title: str, pdf_path: Path) -> int:
    """Ingest a PDF through the complete acquisition, extraction, and indexing pipeline."""
    print(f"\n--- Ingesting: {title} ({pdf_path.name}) ---")
    source_id = acquire.create_source(
        title=title,
        kind=SourceKind.PDF,
        origin=SourceOrigin.UPLOAD,
        original_filename=pdf_path.name,
    )
    dest_path = acquire.media_path_for(source_id, pdf_path.name)
    shutil.copy2(pdf_path, dest_path)
    file_size = dest_path.stat().st_size

    with session_scope() as session:
        src = session.get(Source, source_id)
        if src:
            src.media_path = str(dest_path)
            src.size_bytes = file_size
            src.status = SourceStatus.PROCESSING

    # 1. Extraction
    await stages.extract(source_id)

    # 2. Vector and FTS5 Indexing
    indexed = await rag_index.index_source(source_id, force=True)

    # 3. Status
    with session_scope() as session:
        src = session.get(Source, source_id)
        meta = dict(src.meta or {}) if src else {}
        unreadable = meta.get("unreadable_pages") or []
        if unreadable:
            src.status = SourceStatus.PARTIALLY_PROCESSED
            src.error = f"{len(unreadable)} unreadable pages require OCR"
        else:
            src.status = SourceStatus.READY
            src.error = None
        status = src.status
        page_count = src.page_count
        seg_count = session.query(Segment).filter(Segment.source_id == source_id).count()

    print(f"  -> Extracted: {page_count} pages, {seg_count} segments")
    print(f"  -> Indexed: {indexed} vector embeddings (sqlite-vec available: {vec_available()})")
    print(f"  -> Status: {status.value}")
    return source_id


async def run_rag_qa(question: str, source_id: int):
    """Execute live RAG retrieval and Ollama inference."""
    print(f"\n=======================================================")
    print(f"QUESTION: {question}")

    # 1. Hybrid Retrieval
    excerpts = await rag.retrieve(question, scope_type="source", scope_id=source_id, top_k=5)
    print(f"Retrieved {len(excerpts)} excerpts:")
    for e in excerpts:
        print(f"  [ID {e.id}] (Page {e.page_no}): {e.text[:90]}...")

    # 2. Render prompt
    system_prompt = prompts.render(
        "chat_system",
        excerpts=[
            {
                "id": excerpt.id,
                "text": excerpt.text,
                "source_title": excerpt.source_title,
                "timestamp": excerpt.timestamp,
            }
            for excerpt in excerpts
        ],
        scope_description=f"Source #{source_id}",
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    # 3. Model Inference (Ollama GPU)
    raw_ans = await gateway.complete_text("chat_answer", messages, max_tokens=512)

    # 4. Citation Sanitization & Evidence Assessment
    clean_ans, cited_ids = validate_answer(raw_ans, excerpts)
    evidence_status = assess_evidence_support(clean_ans, cited_ids, excerpts)

    print(f"\nMODEL ANSWER:\n{clean_ans}")
    print(f"CITED IDS: {cited_ids}")
    print(f"EVIDENCE SUPPORT: {evidence_status}")

    return {
        "question": question,
        "raw": raw_ans,
        "clean": clean_ans,
        "cited_ids": cited_ids,
        "evidence": evidence_status,
        "excerpts": excerpts,
    }


async def main():
    print("=======================================================")
    print("EDUVERSE AI: LIVE CURRICULUM PIPELINE VERIFICATION")
    print("=======================================================")

    canonical_data = Path(r"S:\SY\SEM 3\MP\EduVerse-AI-repo\EduVerse-AI-Complete\apps\fullstack\data")
    cfg = Config(data_dir=canonical_data)
    set_config(cfg)
    init_database(cfg)

    # Real PDF 1: Full Project Report
    p1 = Path(r"S:\SY\SEM 3\MP\EduVerse-AI-repo\EduVerse-AI-Complete\academic\report\EduVerse_AI_Project_Report.pdf")
    # Real PDF 2: Two-Page Summary Report
    p2 = Path(r"S:\SY\SEM 3\MP\EduVerse-AI-repo\EduVerse-AI-Complete\academic\report\EduVerse_AI_Two_Page_Report.pdf")
    # Real PDF 3: Synthetic Curriculum Material
    tmp_curr = canonical_data / "fixtures"
    tmp_curr.mkdir(parents=True, exist_ok=True)
    p3 = create_curriculum_pdf(tmp_curr / "Database_Concurrency_Curriculum.pdf")

    s1 = await ingest_document("EduVerse AI Project Report", p1)
    s2 = await ingest_document("EduVerse AI Two Page Report", p2)
    s3 = await ingest_document("Database Concurrency Curriculum", p3)

    # Test Q1: Specific factual fact on Source 3
    q1_res = await run_rag_qa(
        "What is the maximum lock wait timeout for distributed 2PC transactions?",
        source_id=s3,
    )
    assert any("350" in e.text for e in q1_res["excerpts"]), "Excerpt failed to retrieve 350ms"
    assert "350" in q1_res["clean"], "Model answer did not state 350 milliseconds"
    assert len(q1_res["cited_ids"]) > 0, "Model did not cite excerpts"

    # Test Q2: Table fact on Source 3
    q2_res = await run_rag_qa(
        "What anomalies are prevented by Serializable Snapshot Isolation according to the table?",
        source_id=s3,
    )
    assert "Write Skew" in q2_res["clean"] or "write skew" in q2_res["clean"], "Model failed to identify Write Skew"

    # Test Q3: Heartbeat fact on Source 3
    q3_res = await run_rag_qa(
        "What is the heartbeat interval for leader leases in Raft?",
        source_id=s3,
    )
    assert "50" in q3_res["clean"], "Model failed to state 50 milliseconds"

    # Test Q4: Factual query on Source 1 (Project Report)
    q4_res = await run_rag_qa(
        "What is the primary objective of EduVerse AI described in the project report?",
        source_id=s1,
    )
    assert len(q4_res["cited_ids"]) > 0, "No citations generated for project report query"

    # Test Q5: Unsupported query (Honest Abstention)
    q5_res = await run_rag_qa(
        "What is the speed of light in vacuum in miles per hour according to this document?",
        source_id=s3,
    )
    print(f"\nAbstention Verification:")
    print(f"Abstention response: {q5_res['clean']}")
    assert any(
        phrase in q5_res["clean"].lower()
        for phrase in ("not contain", "couldn't find", "does not cover", "not mention", "insufficient evidence")
    ), "Model did not honestly abstain on unsupported question"

    # --- Phase 6.4: Backend Restart & Persistence Verification ---
    print("\n--- Verifying Database & Index Persistence Across Simulated Restart ---")
    # Reset in-memory index pointer and cache to simulate fresh server process startup
    rag_index.set_index(None)
    reloaded_index = rag_index.get_index()
    print(f"  -> Server restarted: Index backend reconnected: {reloaded_index.name}")
    print(f"  -> Total vectors in persisted store: {reloaded_index.count()}")
    assert reloaded_index.count() >= 52, "Persisted vector count mismatch after restart"

    # Execute query without re-ingesting
    restart_qa = await run_rag_qa(
        "What is the maximum lock wait timeout for distributed 2PC transactions?",
        source_id=s3,
    )
    assert "350" in restart_qa["clean"], "Post-restart QA failed to retrieve 350ms"
    assert len(restart_qa["cited_ids"]) > 0, "Post-restart QA missing citations"
    print("  -> Post-restart QA verified: returned 350ms with valid citation [ID]")

    print("\n=======================================================")
    print("ALL LIVE CURRICULUM RAG & RESTART VERIFICATIONS SUCCEEDED!")
    print("=======================================================")


if __name__ == "__main__":
    asyncio.run(main())
