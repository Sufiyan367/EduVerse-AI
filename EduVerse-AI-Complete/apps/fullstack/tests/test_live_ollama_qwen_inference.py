"""Comprehensive live verification suite for local Ollama + Qwen3.5:4b on NVIDIA RTX 3050.

Validates:
1. Multi-step reasoning with native think="high" mode.
2. Mathematical reasoning with step-by-step KaTeX / formula execution.
3. Programming / algorithmic code generation (data structures, time complexity).
4. Full RAG Document QA over an ingested academic PDF with source citations.
5. Strict evidence grounding: abstention on ungrounded/unsupported questions.
6. Privacy contract: internal <think>...</think> tokens are completely scrubbed.
7. NVIDIA GPU offload: verifying VRAM allocation on the RTX 3050 GPU.
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import fitz
import httpx
import pytest

from quicklearn.api.chat import (
    NO_CONTEXT_FALLBACK,
    assess_evidence_support,
    send_message,
    validate_answer,
    SendMessageRequest,
)
from quicklearn.config import Config
from quicklearn.db.enums import ChatScope, SourceKind, SourceOrigin, SourceStatus
from quicklearn.db.models import Chat, Segment, Source
from quicklearn.db.session import session_scope
from quicklearn.pipeline.extract.document import extract_pdf
from quicklearn.pipeline.segment import build_segments, persist_segments
from quicklearn.providers import gateway, registry
from quicklearn.providers.base import text_message
from quicklearn.providers.llm.ollama import OllamaLLM, _clean_thinking_trace
from quicklearn.rag.index import get_index, index_source
from quicklearn.rag.retrieve import retrieve
from quicklearn.settings import get_settings


@pytest.fixture
def ollama_qwen_llm():
    """Return configured OllamaLLM targeting local Qwen3.5:4b with high reasoning."""
    return OllamaLLM(
        base_url="http://127.0.0.1:11434",
        model="qwen3.5:4b",
        think="high",
        num_ctx=4096,
        keep_alive="10m",
    )


@pytest.fixture
def sample_academic_pdf(tmp_path: Path) -> Path:
    """Generate a multi-page academic PDF with known distributed systems & database facts."""
    pdf_path = tmp_path / "distributed_systems_core.pdf"
    doc = fitz.open()

    p1 = doc.new_page(width=612, height=792)
    p1.insert_textbox(
        fitz.Rect(50, 40, 560, 80),
        "Distributed Database Management & Concurrency Control",
        fontsize=16,
    )
    p1.insert_textbox(
        fitz.Rect(50, 90, 560, 320),
        "Section 1: Two-Phase Locking Protocols.\n\n"
        "Concurrency control is essential for ensuring transaction serializability in relational databases. "
        "The standard Two-Phase Locking (2PL) protocol requires each transaction to acquire locks during a "
        "Growing Phase and release them during a Shrinking Phase. However, standard 2PL permits cascading aborts. "
        "To resolve this vulnerability, Strict Two-Phase Locking (Strict 2PL) is introduced. "
        "Strict 2PL mandates that all exclusive (write) locks acquired by a transaction must be held until "
        "the transaction explicitly completes via Commit or Abort. By doing so, Strict 2PL guarantees that "
        "uncommitted dirty writes are never exposed to concurrent transactions, completely preventing cascading aborts.",
        fontsize=11,
    )
    p1.insert_textbox(
        fitz.Rect(50, 340, 560, 550),
        "Section 2: Two-Phase Commit (2PC) Consensus.\n\n"
        "Atomic commitment across distributed partitions is governed by the Two-Phase Commit (2PC) protocol. "
        "In Phase 1 (Prepare), the coordinator broadcasts a PREPARE message to all cohort participants. "
        "Each cohort writes uncommitted state to durable storage and responds with VOTE_COMMIT or VOTE_ABORT. "
        "In Phase 2 (Commit/Abort), if all cohorts voted to commit, the coordinator broadcasts GLOBAL_COMMIT; "
        "otherwise, if any cohort voted abort or timed out, it broadcasts GLOBAL_ABORT. "
        "2PC ensures ACID atomicity across arbitrary network topologies.",
        fontsize=11,
    )

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_nvidia_gpu_offload_active():
    """Verify that NVIDIA GPU offload is active on RTX 3050 and VRAM is allocated."""
    smi = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert smi.returncode == 0, "nvidia-smi failed or NVIDIA driver not present"
    out = smi.stdout.strip()
    parts = [p.strip() for p in out.split(",")]
    assert len(parts) >= 3, f"Unexpected nvidia-smi format: {out}"

    gpu_name = parts[0]
    used_vram_mb = int(parts[1])
    total_vram_mb = int(parts[2])

    assert "GeForce" in gpu_name or "RTX" in gpu_name or "NVIDIA" in gpu_name
    assert total_vram_mb >= 4000, f"Expected at least 4GB VRAM, got {total_vram_mb} MB"
    assert used_vram_mb >= 2000, f"Expected Qwen model offloaded in VRAM (>=2000 MB), got {used_vram_mb} MB"


@pytest.mark.asyncio
async def test_qwen_direct_reasoning_multistep(ollama_qwen_llm: OllamaLLM):
    """Test multi-step reasoning directly with Qwen3.5:4b think='high'."""
    prompt = (
        "Explain how the Two-Phase Commit (2PC) protocol guarantees atomicity across distributed nodes. "
        "Detail what happens during Phase 1 (Prepare) versus Phase 2 (Commit/Abort)."
    )
    resp = await ollama_qwen_llm.complete(
        [text_message("user", prompt)],
        model="qwen3.5:4b",
        temperature=0.2,
    )

    assert resp.text and len(resp.text) > 100
    assert "<think>" not in resp.text, "Privacy violation: <think> tag leaked into final text"
    assert "</think>" not in resp.text, "Privacy violation: </think> tag leaked into final text"

    text_lower = resp.text.lower()
    assert "prepare" in text_lower or "phase 1" in text_lower
    assert "commit" in text_lower or "abort" in text_lower
    assert "coordinator" in text_lower or "cohort" in text_lower or "participant" in text_lower or "node" in text_lower


@pytest.mark.asyncio
async def test_qwen_direct_reasoning_mathematical(ollama_qwen_llm: OllamaLLM):
    """Test step-by-step mathematical reasoning and formula evaluation."""
    prompt = (
        "A classification model is evaluated on a test set. There are 400 positive examples and 600 negative examples. "
        "The model predicts 300 positive labels, out of which 240 are true positives. "
        "Calculate: 1) Precision, 2) Recall, and 3) F1-Score. Show each step and the exact decimal values."
    )
    resp = await ollama_qwen_llm.complete(
        [text_message("user", prompt)],
        model="qwen3.5:4b",
        temperature=0.1,
    )

    assert "<think>" not in resp.text
    # Precision = 240 / 300 = 0.80 (80%)
    # Recall = 240 / 400 = 0.60 (60%)
    # F1 = 2 * (0.8 * 0.6) / (0.8 + 0.6) = 0.96 / 1.4 = 0.6857 (or ~0.686)
    text = resp.text
    assert "0.8" in text or "80%" in text, f"Precision 0.8 not found in: {text[:200]}"
    assert "0.6" in text or "60%" in text, f"Recall 0.6 not found in: {text[:200]}"
    assert ("0.68" in text or "0.69" in text or "68.5" in text or "68.6" in text), f"F1 ~0.686 not found in: {text[:200]}"


@pytest.mark.asyncio
async def test_qwen_direct_reasoning_programming(ollama_qwen_llm: OllamaLLM):
    """Test programming algorithms and complexity analysis."""
    prompt = (
        "Write a Python function `two_sum(nums: list[int], target: int) -> list[int]` that finds "
        "the indices of two numbers that add up to target in O(n) time using a hash map. "
        "Explain the time and space complexity."
    )
    resp = await ollama_qwen_llm.complete(
        [text_message("user", prompt)],
        model="qwen3.5:4b",
        temperature=0.2,
    )

    assert "<think>" not in resp.text
    assert "def two_sum" in resp.text
    assert "O(n)" in resp.text or "O(N)" in resp.text


@pytest.mark.asyncio
async def test_qwen_rag_qa_over_academic_pdf(sample_academic_pdf: Path, config: Config, store: Any):
    """Test end-to-end RAG QA: upload academic PDF, index, query via Qwen3.5:4b, verify citations."""
    settings = get_settings()
    settings.set_many({
        "routing.standard": {"provider": "ollama", "model": "qwen3.5:4b"},
        "routing.fast": {"provider": "ollama", "model": "qwen3.5:4b"},
    })
    registry.reset()

    # 1. Ingest document
    extracted = await extract_pdf(sample_academic_pdf)
    segments = build_segments(extracted.units, timed=False)

    with session_scope() as session:
        src = Source(
            title="Distributed Systems & Concurrency",
            kind=SourceKind.PDF,
            origin=SourceOrigin.UPLOAD,
            status=SourceStatus.READY,
            media_path=str(sample_academic_pdf),
            original_filename="distributed_systems_core.pdf",
        )
        session.add(src)
        session.flush()
        source_id = src.id

    persist_segments(source_id, segments)
    await index_source(source_id)

    # 2. Query document via RAG retrieve
    question = "What does Strict Two-Phase Locking (Strict 2PL) prevent and why?"
    hits = await retrieve(question, scope_type="source", scope_id=source_id, top_k=6)
    assert len(hits) > 0, "Retrieval returned no excerpts for Strict 2PL"

    # Build prompt and complete with Qwen3.5:4b
    context_blocks = "\n\n".join(f"[{h.id}] {h.text}" for h in hits)
    system_prompt = (
        "You are an academic tutor. Answer the student's question using ONLY the provided sources. "
        "You MUST anchor every factual statement with bracketed citation markers like [id]. "
        f"\n\nSources:\n{context_blocks}"
    )
    llm = registry.get_llm("standard").provider
    resp = await llm.complete(
        [
            text_message("system", system_prompt),
            text_message("user", question),
        ],
        model="qwen3.5:4b",
        temperature=0.2,
    )

    assert "<think>" not in resp.text
    clean_ans, citations = validate_answer(resp.text, hits)

    assert len(citations) > 0, f"Expected verified citations in answer: {resp.text}"
    assert "abort" in clean_ans.lower()
    support = assess_evidence_support(clean_ans, citations, hits)
    assert support in ("strong", "partial")


@pytest.mark.asyncio
async def test_qwen_rag_abstains_on_unsupported_query(sample_academic_pdf: Path, config: Config, store: Any):
    """Verify that Qwen3.5:4b honestly abstains without hallucinating on questions outside the PDF."""
    settings = get_settings()
    settings.set_many({
        "routing.standard": {"provider": "ollama", "model": "qwen3.5:4b"},
        "routing.fast": {"provider": "ollama", "model": "qwen3.5:4b"},
    })
    registry.reset()

    extracted = await extract_pdf(sample_academic_pdf)
    segments = build_segments(extracted.units, timed=False)

    with session_scope() as session:
        src = Source(
            title="Distributed Systems & Concurrency",
            kind=SourceKind.PDF,
            origin=SourceOrigin.UPLOAD,
            status=SourceStatus.READY,
            media_path=str(sample_academic_pdf),
            original_filename="distributed_systems_core.pdf",
        )
        session.add(src)
        session.flush()
        source_id = src.id

    persist_segments(source_id, segments)
    await index_source(source_id)

    # Query out-of-domain topic
    question = "What is the secret recipe for traditional Italian tiramisu?"
    hits = await retrieve(question, scope_type="source", scope_id=source_id, top_k=6)

    context_blocks = "\n\n".join(f"[{h.id}] {h.text}" for h in hits) if hits else "None"
    system_prompt = (
        "You are an academic tutor. Answer the student's question using ONLY the provided sources. "
        "If the answer cannot be found in the provided sources, explicitly state that the course material "
        "does not contain this information. Do NOT guess or hallucinate."
        f"\n\nSources:\n{context_blocks}"
    )
    llm = registry.get_llm("standard").provider
    resp = await llm.complete(
        [
            text_message("system", system_prompt),
            text_message("user", question),
        ],
        model="qwen3.5:4b",
        temperature=0.1,
    )

    clean_ans, citations = validate_answer(resp.text, hits)
    assert citations == [], f"Should not cite document for ungrounded question, got: {citations}"
    lower = clean_ans.lower()
    assert (
        "not contain" in lower
        or "does not mention" in lower
        or "could not find" in lower
        or "no information" in lower
        or "not found" in lower
        or "not covered" in lower
        or "cannot be found" in lower
    ), f"Expected honest abstention, got: {clean_ans}"
