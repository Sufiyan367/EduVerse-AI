"""Tests for user data isolation and ownership enforcement (PRD & Acceptance Gate).

Verifies that:
1. Two distinct authenticated users (Alice and Bob) have strict data boundaries.
2. Authenticated User Bob cannot read, modify, or delete Alice's sources (HTTP 403 Forbidden).
3. Authenticated User Bob cannot read or modify Alice's notes (HTTP 403 Forbidden).
4. Authenticated User Bob cannot view, update, or delete Alice's scheduled revision sessions (HTTP 403 Forbidden).
5. Alice has full read, modify, and delete access to her own records (HTTP 200 OK).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from quicklearn.auth import create_access_token, hash_password
from quicklearn.config import Config
from quicklearn.db.enums import SourceKind, SourceOrigin, SourceStatus
from quicklearn.db.models import Note, RevisionSession, Source, User
from quicklearn.db.session import session_scope
from quicklearn.main import create_app


@pytest.fixture
def client(config: Config) -> TestClient:
    app = create_app(config)
    return TestClient(app)


@pytest.fixture
def alice_and_bob(client: TestClient) -> tuple[dict[str, str], dict[str, str], int, int]:
    """Create two active users in the database and return their auth headers and IDs."""
    with session_scope() as session:
        alice = User(
            email="alice@eduverse.ai",
            username="alice",
            hashed_password=hash_password("alice123"),
            full_name="Alice Scholar",
            avatar_color="#7C3AED",
            is_active=True,
        )
        bob = User(
            email="bob@eduverse.ai",
            username="bob",
            hashed_password=hash_password("bob123"),
            full_name="Bob Learner",
            avatar_color="#06B6D4",
            is_active=True,
        )
        session.add(alice)
        session.add(bob)
        session.flush()
        alice_id = alice.id
        bob_id = bob.id

    alice_token = create_access_token(alice_id, "alice", "alice@eduverse.ai")
    bob_token = create_access_token(bob_id, "bob", "bob@eduverse.ai")

    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    return alice_headers, bob_headers, alice_id, bob_id


# =========================================================================
# 1. SOURCE ISOLATION TESTS
# =========================================================================

def test_cross_user_source_isolation(client: TestClient, alice_and_bob):
    alice_headers, bob_headers, alice_id, bob_id = alice_and_bob

    # Alice creates a text source
    resp = client.post(
        "/api/v1/sources/text",
        json={"title": "Alice Confidential Notes", "content": "Database Normalization Third Normal Form"},
        headers=alice_headers,
    )
    assert resp.status_code == 200, resp.text
    source_id = resp.json()["source_id"]

    # Verify database assigns user_id = alice_id
    with session_scope() as session:
        source = session.get(Source, source_id)
        assert source is not None
        assert source.user_id == alice_id

    # Bob attempts to read Alice's source -> 403 Forbidden
    get_resp = client.get(f"/api/v1/sources/{source_id}", headers=bob_headers)
    assert get_resp.status_code == 403
    assert "ForbiddenError" in get_resp.json()["error"]

    # Bob attempts to modify Alice's source -> 403 Forbidden
    patch_resp = client.patch(
        f"/api/v1/sources/{source_id}",
        json={"title": "Hacked Title by Bob"},
        headers=bob_headers,
    )
    assert patch_resp.status_code == 403
    assert "ForbiddenError" in patch_resp.json()["error"]

    # Bob attempts to delete Alice's source -> 403 Forbidden
    del_resp = client.delete(f"/api/v1/sources/{source_id}", headers=bob_headers)
    assert del_resp.status_code == 403
    assert "ForbiddenError" in del_resp.json()["error"]

    # Alice accesses her own source -> 200 OK
    alice_get = client.get(f"/api/v1/sources/{source_id}", headers=alice_headers)
    assert alice_get.status_code == 200
    assert alice_get.json()["source"]["title"] == "Alice Confidential Notes"

    # Alice modifies her own source -> 200 OK
    alice_patch = client.patch(
        f"/api/v1/sources/{source_id}",
        json={"title": "Alice Updated Notes"},
        headers=alice_headers,
    )
    assert alice_patch.status_code == 200
    assert alice_patch.json()["title"] == "Alice Updated Notes"


# =========================================================================
# 2. NOTE ISOLATION TESTS
# =========================================================================

def test_cross_user_note_isolation(client: TestClient, alice_and_bob):
    alice_headers, bob_headers, alice_id, bob_id = alice_and_bob

    # Seed a source and note belonging to Alice
    with session_scope() as session:
        source = Source(
            title="Alice Source",
            kind=SourceKind.TEXT,
            origin=SourceOrigin.PASTE,
            user_id=alice_id,
            status=SourceStatus.READY,
        )
        session.add(source)
        session.flush()

        note = Note(
            source_id=source.id,
            user_id=alice_id,
            title="Alice Private Note",
            doc={"type": "doc", "content": [{"type": "paragraph", "text": "Secret exam answers"}]},
        )
        session.add(note)
        session.flush()
        note_id = note.id

    # Bob attempts to get Alice's note -> 403 Forbidden
    get_resp = client.get(f"/api/v1/notes/{note_id}", headers=bob_headers)
    assert get_resp.status_code == 403
    assert "ForbiddenError" in get_resp.json()["error"]

    # Bob attempts to patch Alice's note -> 403 Forbidden
    patch_resp = client.patch(
        f"/api/v1/notes/{note_id}",
        json={"title": "Bob Tampered Note"},
        headers=bob_headers,
    )
    assert patch_resp.status_code == 403
    assert "ForbiddenError" in patch_resp.json()["error"]

    # Alice accesses her own note -> 200 OK
    alice_get = client.get(f"/api/v1/notes/{note_id}", headers=alice_headers)
    assert alice_get.status_code == 200
    assert alice_get.json()["title"] == "Alice Private Note"


# =========================================================================
# 3. REVISION SESSION ISOLATION TESTS
# =========================================================================

def test_cross_user_revision_isolation(client: TestClient, alice_and_bob):
    alice_headers, bob_headers, alice_id, bob_id = alice_and_bob

    # Alice schedules a revision session
    sched_resp = client.post(
        "/api/v1/revision-planner/schedule",
        json={
            "topic": "Alice Exam Prep Topic",
            "priority": "HIGH",
            "recommended_duration_min": 30,
            "reason": "Final review",
        },
        headers=alice_headers,
    )
    assert sched_resp.status_code == 201, sched_resp.text
    session_id = sched_resp.json()["id"]
    assert sched_resp.json()["user_id"] == alice_id

    # Bob lists sessions -> Bob should not see Alice's session
    bob_list = client.get("/api/v1/revision-planner/sessions", headers=bob_headers)
    assert bob_list.status_code == 200
    bob_session_ids = [s["id"] for s in bob_list.json()]
    assert session_id not in bob_session_ids

    # Bob attempts to update Alice's session status -> 403 Forbidden
    bob_patch = client.patch(
        f"/api/v1/revision-planner/sessions/{session_id}",
        json={"status": "COMPLETED"},
        headers=bob_headers,
    )
    assert bob_patch.status_code == 403
    assert "ForbiddenError" in bob_patch.json()["error"]

    # Bob attempts to delete Alice's session -> 403 Forbidden
    bob_del = client.delete(
        f"/api/v1/revision-planner/sessions/{session_id}",
        headers=bob_headers,
    )
    assert bob_del.status_code == 403
    assert "ForbiddenError" in bob_del.json()["error"]

    # Alice lists sessions -> Sees her session
    alice_list = client.get("/api/v1/revision-planner/sessions", headers=alice_headers)
    assert alice_list.status_code == 200
    assert any(s["id"] == session_id for s in alice_list.json())

    # Alice updates her session -> 200 OK
    alice_patch = client.patch(
        f"/api/v1/revision-planner/sessions/{session_id}",
        json={"status": "COMPLETED", "notes": "Studied all 30 mins"},
        headers=alice_headers,
    )
    assert alice_patch.status_code == 200
    assert alice_patch.json()["status"] == "COMPLETED"

    # Alice deletes her session -> 200 OK
    alice_del = client.delete(
        f"/api/v1/revision-planner/sessions/{session_id}",
        headers=alice_headers,
    )
    assert alice_del.status_code == 200
