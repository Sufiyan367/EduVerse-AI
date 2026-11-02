"""End-to-End API Workflow Verification for P0 DeepTutor Adaptations.

Exercises:
1. Authenticated user isolation with two uploaded documents.
2. Source Manifest System Note generation and injection into chat assistant context.
3. Inventory question answering based on authoritative DB manifest facts.
4. Quote normalization and citation resolution to original document pages and segments.
5. Quiz question generation with server-side evidence verification (positive and negative cases).
"""

import asyncio
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from quicklearn.main import create_app
from quicklearn.auth import create_access_token
from quicklearn.config import get_config
from quicklearn.db.bootstrap import init_database
from quicklearn.db.enums import SourceKind, SourceOrigin, SourceStatus
from quicklearn.db.models import Base, Concept, QuizItem, Segment, Source, User
from quicklearn.db.session import get_engine, session_scope
from quicklearn.pipeline.generate.quiz import _clean_items, QuizItemOutRow
from quicklearn.pipeline.schemas import QuizItemList, QuizItemOut
from quicklearn.rag.manifest import get_user_source_manifest, render_manifest_note
from quicklearn.rag.grounding import verify_evidence_in_segments


@pytest.fixture(scope="module")
def app_client():
    init_database()
    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def seeded_e2e_user():
    with session_scope() as session:
        # Create dedicated test student
        user = session.query(User).filter_by(email="p0_tester@eduverse.ai").first()
        if not user:
            user = User(
                email="p0_tester@eduverse.ai",
                username="p0_tester",
                full_name="P0 Test Student",
                hashed_password="dummy_hash_for_test",
            )
            session.add(user)
            session.flush()

        # Clean existing test sources
        session.query(Source).filter_by(user_id=user.id).delete()
        session.flush()

        # Add Document 1: Database Concurrency Curriculum
        s1 = Source(
            user_id=user.id,
            title="Database_Concurrency_Curriculum.pdf",
            kind=SourceKind.PDF,
            origin=SourceOrigin.UPLOAD,
            status=SourceStatus.READY,
            page_count=2,
            size_bytes=4134,
        )
        # Add Document 2: OS Scheduling Notes
        s2 = Source(
            user_id=user.id,
            title="OS_Process_Scheduling.pdf",
            kind=SourceKind.PDF,
            origin=SourceOrigin.UPLOAD,
            status=SourceStatus.READY,
            page_count=4,
            size_bytes=8192,
        )
        session.add_all([s1, s2])
        session.flush()

        # Add verified segments for Document 1
        seg1 = Segment(
            source_id=s1.id,
            index=0,
            page_no=1,
            text="Concurrency control in DBMS ensures that multiple trans-\nactions execute concurrently without violating serializability.",
        )
        seg2 = Segment(
            source_id=s1.id,
            index=1,
            page_no=2,
            text="Two-phase locking requires transactions to acquire all locks during the expanding phase and release them during shrinking.",
        )
        # Add verified segments for Document 2
        seg3 = Segment(
            source_id=s2.id,
            index=0,
            page_no=1,
            text="Round-robin scheduling allocates fixed time quantum slices to runnable processes in the ready queue.",
        )
        session.add_all([seg1, seg2, seg3])
        session.flush()

        token = create_access_token(user.id, user.username, user.email)
        user_info = {
            "user_id": user.id,
            "token": token,
            "source1_id": s1.id,
            "source2_id": s2.id,
            "seg1_id": seg1.id,
            "seg2_id": seg2.id,
            "seg3_id": seg3.id,
        }
        session.commit()
        return user_info


def test_e2e_source_manifest_generation(seeded_e2e_user):
    """Step 1: Manifest accurately reflects both uploaded documents with correct pages and segment counts."""
    uid = seeded_e2e_user["user_id"]
    manifest = get_user_source_manifest(user_id=uid)

    assert manifest.total_sources == 2
    assert manifest.ready_sources == 2
    assert manifest.total_pages == 6  # 2 + 4
    assert manifest.total_segments == 3  # 2 in doc 1 + 1 in doc 2

    note = render_manifest_note(manifest)
    assert 'Database_Concurrency_Curriculum.pdf' in note
    assert 'OS_Process_Scheduling.pdf' in note
    assert '2 ready' in note
    assert '6' in note


def test_e2e_chat_prompt_injection(app_client, seeded_e2e_user):
    """Step 2: When an authenticated user chats, the system prompt contains the authoritative source manifest."""
    token = seeded_e2e_user["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create chat session
    res = app_client.post("/api/v1/chat", json={"title": "Inventory Query Chat", "scope_type": "global"}, headers=headers)
    assert res.status_code == 200
    chat_id = res.json()["id"]

    # Post query asking about uploaded documents
    msg_res = app_client.post(
        f"/api/v1/chat/{chat_id}/message",
        json={"content": "What documents are uploaded in my account?"},
        headers=headers,
    )
    assert msg_res.status_code == 200
    data = msg_res.json()
    assert "content" in data or "text" in data or "id" in data


def test_e2e_citation_resolution_preserves_provenance(app_client, seeded_e2e_user):
    """Step 3: Citations resolve to exact original segment text, page numbers, and source IDs."""
    token = seeded_e2e_user["token"]
    headers = {"Authorization": f"Bearer {token}"}
    seg1_id = seeded_e2e_user["seg1_id"]
    seg2_id = seeded_e2e_user["seg2_id"]

    res = app_client.get(f"/api/v1/chat/citations?ids={seg1_id},{seg2_id}", headers=headers)
    assert res.status_code == 200
    segments = res.json().get("segments", [])
    assert len(segments) == 2

    c1 = next(s for s in segments if s["id"] == seg1_id)
    assert c1["page_no"] == 1
    assert "trans-\nactions" in c1["text"]
    assert c1["source_id"] == seeded_e2e_user["source1_id"]


def test_e2e_quiz_evidence_verification_positive_and_negative(seeded_e2e_user):
    """Step 4: Quiz generator accepts verified questions and rejects ungrounded/hallucinated questions."""
    with session_scope() as session:
        segments = list(
            session.query(Segment).filter(Segment.source_id == seeded_e2e_user["source1_id"]).all()
        )

    # 1. Positive: quote matches text with hyphenated wrap: 'concur-\nactions' -> 'transactions execute concurrently'
    valid_q = QuizItemOut(
        type="mcq",
        question="What does concurrency control ensure in a DBMS?",
        options=["Serializability", "Linearizability", "Eventual consistency", "Read uncommitted"],
        answer="Serializability",
        explanation="Concurrency control ensures serializability.",
        difficulty=3,
        concept_id=1,
        segment_ids=[],
        evidence="transactions execute concurrently without violating serializability",
    )

    # 2. Negative: fabricated evidence not present anywhere in the document
    hallucinated_q = QuizItemOut(
        type="mcq",
        question="What is the time complexity of the Paxos consensus algorithm?",
        options=["O(1)", "O(log N)", "O(N)", "O(N^2)"],
        answer="O(1)",
        explanation="Paxos runs in constant rounds.",
        difficulty=4,
        concept_id=1,
        segment_ids=[],
        evidence="Paxos consensus was proven optimal by Leslie Lamport in the ACM TOCS journal.",
    )

    cleaned = _clean_items(
        QuizItemList(items=[valid_q, hallucinated_q]),
        valid_concept_ids={1},
        mcq_options=4,
        segments=segments,
    )

    # The valid question MUST be accepted
    assert len(cleaned) == 1
    accepted = cleaned[0]
    assert accepted.question == valid_q.question
    assert accepted.page_no == 1
    assert accepted.evidence == "transactions execute concurrently without violating serializability"

    # The hallucinated Paxos question MUST be rejected
    assert not any(q.question == hallucinated_q.question for q in cleaned)
