"""Remediation verification test suite for all six Astra Priority 0 defect findings.

Strictly verifies:
1. Ownership enforcement across sources, notes, cards, settings, and dashboard.
   Missing auth -> 401/403. Mismatched user -> 403. Invalid token -> 401.
2. Insecure fallback signing key removed; forged tokens with default secret or missing exp rejected.
3. Quiz submissions are idempotent; retries do not inflate mastery or duplicate attempts.
   Finished sessions and out-of-scope questions are rejected.
4. AI grading failure does not penalize mastery (0.8 remains 0.8 on provider timeout/429).
5. Flashcard review undo completely restores both FSRS scheduling and concept mastery (0.3 -> 0.0).
6. Unsupported answers with fabricated citations fail closed or abstain rather than surviving as facts.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from quicklearn import auth
from quicklearn.api.chat import NO_CONTEXT_FALLBACK, validate_answer
from quicklearn.db.bootstrap import init_database
from quicklearn.db.enums import QuizItemType, QuizMode, SourceKind, SourceOrigin, SourceStatus
from quicklearn.db.models import Card, Concept, Note, QuizAttempt, QuizItem, QuizSession, Review, Source, User
from quicklearn.db.session import dispose_engine, session_scope
from quicklearn.main import create_app
from quicklearn.rag.retrieve import Excerpt


@pytest.fixture
def remediation_client(store, config):
    """Seed Alice and Bob in an isolated test database and return client and tokens."""
    with session_scope() as session:
        alice = User(
            email="remed-alice@eduverse.ai",
            username="remed_alice",
            hashed_password=auth.hash_password("alice-secret-123"),
            is_active=True,
        )
        bob = User(
            email="remed-bob@eduverse.ai",
            username="remed_bob",
            hashed_password=auth.hash_password("bob-secret-123"),
            is_active=True,
        )
        session.add_all([alice, bob])
        session.flush()

        src = Source(
            title="Alice Confidential Machine Learning",
            kind=SourceKind.TEXT,
            origin=SourceOrigin.PASTE,
            status=SourceStatus.READY,
            user_id=alice.id,
        )
        session.add(src)
        session.flush()

        concept = Concept(
            source_id=src.id,
            name="Gradient Descent Optimization",
            definition="First-order iterative optimization algorithm for finding a local minimum.",
            mastery=0.0,
        )
        note = Note(
            source_id=src.id,
            user_id=alice.id,
            title="Alice Private Notes",
            doc={"type": "doc", "content": []},
        )
        session.add_all([concept, note])
        session.flush()

        card = Card(
            source_id=src.id,
            concept_id=concept.id,
            front="What is gradient descent?",
            back="An optimization algorithm to minimize loss.",
        )
        item = QuizItem(
            source_id=src.id,
            concept_id=concept.id,
            type=QuizItemType.MCQ,
            question="Is gradient descent an optimization method?",
            options=["yes", "no"],
            answer="yes",
        )
        qs = QuizSession(
            user_id=alice.id,
            mode=QuizMode.PRACTICE,
            source_ids=[src.id],
            length=1,
        )
        session.add_all([card, item, qs])
        session.flush()

        ids = {
            "source": src.id,
            "note": note.id,
            "card": card.id,
            "item": item.id,
            "session": qs.id,
            "concept": concept.id,
            "alice": alice.id,
            "bob": bob.id,
        }

    alice_token = auth.create_access_token(alice.id, alice.username, alice.email)
    bob_token = auth.create_access_token(bob.id, bob.username, bob.email)

    client = TestClient(create_app(config))
    return client, ids, {"Authorization": f"Bearer {alice_token}"}, {"Authorization": f"Bearer {bob_token}"}


# =========================================================================
# DEFECT 1: ANONYMOUS ACCESS AND OWNERSHIP BYPASS (A01, A02, A04)
# =========================================================================

def test_remediation_ownership_enforced_on_sources_and_notes(remediation_client):
    client, ids, alice_hdr, bob_hdr = remediation_client

    # 1. Bob cannot read Alice's source -> 403 Forbidden
    r_bob = client.get(f"/api/v1/sources/{ids['source']}", headers=bob_hdr)
    assert r_bob.status_code == 404, f"Bob could discover Alice source: {r_bob.text}"

    # 2. Anonymous cannot read Alice's source -> 403 Forbidden
    r_anon = client.get(f"/api/v1/sources/{ids['source']}")
    assert r_anon.status_code == 401, f"Anonymous could read Alice source: {r_anon.text}"

    # 3. Invalid token is rejected -> 401 Unauthorized (NOT bypassed as anonymous!)
    r_invalid = client.get(f"/api/v1/sources/{ids['source']}", headers={"Authorization": "Bearer invalid-garbage-token"})
    assert r_invalid.status_code == 401, f"Invalid token was not rejected with 401: {r_invalid.status_code}"

    # 4. Anonymous cannot read Alice's note -> 403 Forbidden
    r_anon_note = client.get(f"/api/v1/notes/{ids['note']}")
    assert r_anon_note.status_code == 401, f"Anonymous could read Alice note: {r_anon_note.text}"

    # 5. Anonymous cannot edit Alice's source -> 403 Forbidden
    r_anon_edit = client.patch(f"/api/v1/sources/{ids['source']}", json={"title": "Hacked Title"})
    assert r_anon_edit.status_code == 401, f"Anonymous could edit Alice source: {r_anon_edit.text}"

    # 6. Alice can read her own source and notes -> 200 OK
    r_alice_src = client.get(f"/api/v1/sources/{ids['source']}", headers=alice_hdr)
    assert r_alice_src.status_code == 200
    r_alice_note = client.get(f"/api/v1/notes/{ids['note']}", headers=alice_hdr)
    assert r_alice_note.status_code == 200


def test_remediation_cards_settings_and_analytics_scoped(remediation_client):
    client, ids, alice_hdr, bob_hdr = remediation_client

    # 1. Bob cannot read Alice's cards when listing -> Alice's card excluded
    r_bob_cards = client.get("/api/v1/cards", headers=bob_hdr)
    assert r_bob_cards.status_code == 200
    bob_card_ids = [c["id"] for c in r_bob_cards.json()["cards"]]
    assert ids["card"] not in bob_card_ids, "Alice's card leaked into Bob's cards list!"

    # 2. Anonymous cannot edit card -> 403 Forbidden
    r_anon_card_edit = client.patch(f"/api/v1/cards/{ids['card']}", json={"front": "Hacked front"})
    assert r_anon_card_edit.status_code == 401, f"Anonymous could edit card: {r_anon_card_edit.status_code}"

    # 3. Anonymous cannot mutate settings -> 401 Unauthorized
    r_anon_settings = client.patch("/api/v1/settings", json={"values": {"onboarding.completed": True}})
    assert r_anon_settings.status_code == 401, f"Anonymous could mutate settings: {r_anon_settings.status_code}"

    # 4. A regular student cannot update installation-wide provider settings.
    r_auth_settings = client.patch("/api/v1/settings", json={"values": {"onboarding.completed": True}}, headers=alice_hdr)
    assert r_auth_settings.status_code == 403

    # 5. Bob's dashboard stats do NOT count Alice's private sources
    r_bob_dash = client.get("/api/v1/dashboard/stats", headers=bob_hdr)
    assert r_bob_dash.status_code == 200
    assert r_bob_dash.json()["total_sources"] == 0, "Bob's dashboard counted Alice's private source!"


def test_remediation_anonymous_upload_rejected(remediation_client):
    client, ids, alice_hdr, bob_hdr = remediation_client

    # Headerless upload must be rejected
    r_anon_up = client.post(
        "/api/v1/sources/upload",
        files={"file": ("test.txt", b"Course contents about linear algebra.", "text/plain")}
    )
    assert r_anon_up.status_code in {401, 403}, f"Anonymous upload was allowed: {r_anon_up.status_code}"

    # Authenticated upload succeeds and records owner
    r_auth_up = client.post(
        "/api/v1/sources/upload",
        files={"file": ("test.txt", b"Course contents about linear algebra.", "text/plain")},
        headers=alice_hdr,
    )
    assert r_auth_up.status_code == 200
    uploaded_source_id = r_auth_up.json()["source_id"]
    with session_scope() as session:
        src = session.get(Source, uploaded_source_id)
        assert src is not None
        assert src.user_id == ids["alice"]


# =========================================================================
# DEFECT 2: INSECURE DEFAULT TOKEN-SIGNING KEY (A03)
# =========================================================================

def test_remediation_insecure_default_key_and_unexpiring_tokens_rejected(remediation_client):
    client, ids, alice_hdr, bob_hdr = remediation_client

    insecure_legacy_fallback = "eduverse-ai-secret-key-salt-2026-secure-token"

    enc = lambda x: base64.urlsafe_b64encode(json.dumps(x).encode()).decode().rstrip("=")
    # 1. Forged token using the old hardcoded fallback string
    header = enc({"alg": "HS256", "typ": "JWT"})
    payload_no_exp = enc({"sub": str(ids["alice"])})
    data = f"{header}.{payload_no_exp}"
    sig = base64.urlsafe_b64encode(hmac.new(insecure_legacy_fallback.encode(), data.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    forged_token = f"{data}.{sig}"

    r_forged = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
    assert r_forged.status_code == 401, "Forged token signed with legacy default key was accepted!"

    # 2. Token signed with the real key BUT missing mandatory 'exp'
    real_secret = auth.get_jwt_secret()
    sig_no_exp = base64.urlsafe_b64encode(hmac.new(real_secret.encode(), data.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    token_missing_exp = f"{data}.{sig_no_exp}"

    r_no_exp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_missing_exp}"})
    assert r_no_exp.status_code == 401, "Token without expiration was accepted!"

    # 3. Expired token is rejected
    now = dt.datetime.now(dt.timezone.utc)
    expired_payload = enc({"sub": str(ids["alice"]), "iat": int(now.timestamp()) - 100, "exp": int(now.timestamp()) - 50})
    data_expired = f"{header}.{expired_payload}"
    sig_expired = base64.urlsafe_b64encode(hmac.new(real_secret.encode(), data_expired.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    token_expired = f"{data_expired}.{sig_expired}"

    r_expired = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_expired}"})
    assert r_expired.status_code == 401, "Expired token was accepted!"


# =========================================================================
# DEFECT 3: DUPLICATE QUIZ SUBMISSIONS INFLATE MASTERY (A05, A07)
# =========================================================================

def test_remediation_quiz_idempotency_and_session_scope(remediation_client):
    client, ids, alice_hdr, bob_hdr = remediation_client
    client.headers.update(alice_hdr)
    url = f"/api/v1/quiz/session/{ids['session']}/answer"
    body = {"item_id": ids["item"], "response": "yes"}

    # First submission: correct answer moves concept mastery from 0.0 -> 0.3
    r1 = client.post(url, json=body)
    assert r1.status_code == 200
    assert r1.json()["mastery"] == 0.3

    # Duplicate submission: must be idempotent!
    r2 = client.post(url, json=body)
    assert r2.status_code == 200
    # Mastery MUST NOT be inflated to 0.51!
    assert r2.json()["mastery"] == 0.3, f"Mastery was inflated on duplicate submission: {r2.json()['mastery']}"
    assert r2.json().get("duplicate") is True

    # Total attempts count in database must strictly be 1!
    with session_scope() as session:
        att_count = session.scalar(select(func.count(QuizAttempt.id)))
    assert att_count == 1, f"Duplicate attempt inserted! Count: {att_count}"

    # Finish the session
    client.get(f"/api/v1/quiz/session/{ids['session']}/results")

    # Third submission after finish: rejected with ValidationError (422/400)
    r3 = client.post(url, json=body)
    assert r3.status_code in {400, 422}, f"Finished session accepted answer: {r3.status_code}"

    # Outside session scope item rejected with ValidationError (422/400)
    with session_scope() as session:
        other_src = Source(title="Other source", kind=SourceKind.TEXT, origin=SourceOrigin.PASTE, status=SourceStatus.READY)
        session.add(other_src)
        session.flush()
        other_concept = Concept(source_id=other_src.id, name="Other", definition="Other")
        session.add(other_concept)
        session.flush()
        outside_item = QuizItem(source_id=other_src.id, concept_id=other_concept.id, type=QuizItemType.MCQ, question="Outside?", options=["a"], answer="a")
        session.add(outside_item)
        session.flush()
        outside_id = outside_item.id

        # Reopen a new session
        qs2 = QuizSession(user_id=ids["alice"], mode=QuizMode.PRACTICE, source_ids=[ids["source"]], length=2)
        session.add(qs2)
        session.flush()
        qs2_id = qs2.id

    r_outside = client.post(f"/api/v1/quiz/session/{qs2_id}/answer", json={"item_id": outside_id, "response": "a"})
    assert r_outside.status_code in {400, 422}, f"Outside scope question was accepted: {r_outside.status_code}"


# =========================================================================
# DEFECT 4: AI/PROVIDER GRADING FAILURES PENALIZE STUDENTS (A06)
# =========================================================================

def test_remediation_provider_failure_does_not_penalize_mastery(remediation_client):
    client, ids, alice_hdr, bob_hdr = remediation_client
    client.headers.update(alice_hdr)

    # Prepare free-response question with student starting mastery = 0.8
    with session_scope() as session:
        session.get(QuizItem, ids["item"]).type = QuizItemType.FREE
        session.get(Concept, ids["concept"]).mastery = 0.8

    # Simulate provider outage / timeout
    with patch("quicklearn.pipeline.generate.quiz.gateway.complete_structured", new=AsyncMock(side_effect=RuntimeError("synthetic provider timeout"))):
        r = client.post(
            f"/api/v1/quiz/session/{ids['session']}/answer",
            json={"item_id": ids["item"], "response": "A thoughtful explanation of gradient descent steps."}
        )

    assert r.status_code == 200
    data = r.json()
    assert data.get("is_graded") is False
    # Student mastery MUST remain 0.8 (NOT halved to 0.4!)
    assert data.get("mastery") == 0.8, f"Student mastery was penalized by provider outage: {data.get('mastery')}"

    # Verify concept mastery in DB remains 0.8
    with session_scope() as session:
        db_mastery = session.get(Concept, ids["concept"]).mastery
    assert db_mastery == 0.8


# =========================================================================
# DEFECT 5: UNDOING FLASHCARD REVIEWS LEAVES MASTERY CHANGED (A08)
# =========================================================================

def test_remediation_review_undo_restores_concept_mastery(remediation_client):
    client, ids, alice_hdr, bob_hdr = remediation_client

    # Concept starts at mastery = 0.0
    with session_scope() as session:
        session.get(Concept, ids["concept"]).mastery = 0.0

    # Alice reviews card as Good (rating 3) -> reps become 1, mastery becomes 0.3
    r_rev = client.post(f"/api/v1/cards/{ids['card']}/review", json={"rating": 3}, headers=alice_hdr)
    assert r_rev.status_code == 200

    with session_scope() as session:
        assert session.get(Card, ids["card"]).reps == 1
        assert session.get(Concept, ids["concept"]).mastery == 0.3

    # Alice undos review -> card reps must return to 0 AND concept mastery MUST return to 0.0
    r_undo = client.post(f"/api/v1/cards/{ids['card']}/undo", headers=alice_hdr)
    assert r_undo.status_code == 200

    with session_scope() as session:
        reps_after = session.get(Card, ids["card"]).reps
        mastery_after = session.get(Concept, ids["concept"]).mastery

    assert reps_after == 0, f"Card repetitions not restored: {reps_after}"
    assert mastery_after == 0.0, f"Concept mastery was not restored on undo! Still at {mastery_after}"


# =========================================================================
# DEFECT 6: UNSUPPORTED ANSWER TEXT SURVIVES CITATION FILTERING (A09)
# =========================================================================

def test_remediation_unsupported_claims_fail_closed_or_abstain():
    excerpt = Excerpt(id=1, text="Water freezes at zero degrees Celsius.", source_id=1, source_title="Thermodynamics")

    # 1. Answer citing only hallucinated citation [999] with no grounding in retrieved text
    text, ids = validate_answer("The Moon is made of green cheese [999].", [excerpt])
    assert ids == []
    # Must abstain or qualify rather than asserting cheese as fact!
    assert "cheese" not in text.lower() or "not contain evidence" in text.lower() or "could not verify" in text.lower()

    # 2. Answer when NO excerpts retrieved and no disclaimer: replaced by NO_CONTEXT_FALLBACK
    text_no_ctx, ids_no_ctx = validate_answer("Albert Einstein developed general relativity in 1915.", [])
    assert ids_no_ctx == []
    assert text_no_ctx == NO_CONTEXT_FALLBACK

    # 3. Grounded answer with valid citation [1] retains valid citation and verified text
    grounded_text, grounded_ids = validate_answer("Water transitions to ice at 0 degrees Celsius [1].", [excerpt])
    assert grounded_ids == [1]
    assert "[1]" in grounded_text
