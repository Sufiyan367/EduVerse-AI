"""Automated tests for EduVerse AI specialized modules:
Authentication, Knowledge Gap Detection, Adaptive Revision Planner, and Dashboard Analytics.
"""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from quicklearn.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from quicklearn.config import Config
from quicklearn.db.models import (
    Card,
    CardState,
    Concept,
    QuizAttempt,
    QuizItem,
    QuizItemType,
    RevisionSession,
    Source,
    SourceKind,
    SourceOrigin,
    User,
)
from quicklearn.db.session import session_scope
from quicklearn.db.types import utcnow
from quicklearn.main import create_app
from quicklearn.study.knowledge_gap import analyze_knowledge_gaps
from quicklearn.study.revision_planner import generate_revision_recommendations


@pytest.fixture
def client(config: Config) -> TestClient:
    app = create_app(config)
    return TestClient(app)


# =========================================================================
# 1. AUTHENTICATION & SECURITY TESTS
# =========================================================================

def test_password_hashing_and_verification():
    pw = "SuperSecretPassword123!"
    hashed = hash_password(pw)
    assert hashed != pw
    assert "$" in hashed
    assert verify_password(pw, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_token_creation_and_validation():
    token = create_access_token(user_id=42, username="student", email="student@eduverse.ai", expires_in_hours=1)
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["username"] == "student"
    assert payload["email"] == "student@eduverse.ai"

    # Corrupt token
    assert decode_access_token(token + "corrupt") is None


def test_auth_registration_and_login_flow(client: TestClient):
    # Register new user
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "jane@example.com",
            "username": "janedoe",
            "password": "Password123",
            "full_name": "Jane Doe",
        },
    )
    assert reg_res.status_code == 201
    data = reg_res.json()
    assert "token" in data
    assert data["user"]["email"] == "jane@example.com"
    assert data["user"]["username"] == "janedoe"
    token = data["token"]

    # Verify /auth/me
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "jane@example.com"

    # Login with username
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "janedoe", "password": "Password123"},
    )
    assert login_res.status_code == 200
    assert "token" in login_res.json()

    # Login with wrong password
    bad_login = client.post(
        "/api/v1/auth/login",
        json={"username": "janedoe", "password": "WrongPassword"},
    )
    assert bad_login.status_code == 401

    # Duplicate registration rejected
    dup_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "jane@example.com",
            "username": "janedoe2",
            "password": "Password123",
            "full_name": "Jane Doe",
        },
    )
    assert dup_res.status_code == 400


def test_default_demo_user_seeded(client: TestClient):
    # The default student@eduverse.ai user should exist and be able to log in
    res = client.post(
        "/api/v1/auth/login",
        json={"username": "student@eduverse.ai", "password": "demo123"},
    )
    assert res.status_code == 200
    assert res.json()["user"]["email"] == "student@eduverse.ai"


# =========================================================================
# 2. KNOWLEDGE GAP DETECTOR TESTS
# =========================================================================

def test_knowledge_gap_identification(client: TestClient):
    with session_scope() as session:
        src = Source(title="Algorithms 101", kind=SourceKind.PDF, origin=SourceOrigin.UPLOAD)
        session.add(src)
        session.flush()

        concept_dp = Concept(source_id=src.id, name="Dynamic Programming", definition="Breaking problem into subproblems")
        concept_graph = Concept(source_id=src.id, name="Graph Theory", definition="Nodes and edges")
        session.add_all([concept_dp, concept_graph])
        session.flush()

        # Item 1 on DP: Student gets wrong
        item1 = QuizItem(
            source_id=src.id,
            concept_id=concept_dp.id,
            type=QuizItemType.MCQ,
            question="What is memoization?",
            options=["Caching", "Sorting", "Hashing", "Greedy"],
            answer="Caching",
            explanation="Memoization stores calculated states.",
        )
        # Item 2 on DP: Student gets wrong again (0% accuracy on DP -> CRITICAL)
        item2 = QuizItem(
            source_id=src.id,
            concept_id=concept_dp.id,
            type=QuizItemType.MCQ,
            question="What is optimal substructure?",
            options=["Property", "Sort", "Tree", "Loop"],
            answer="Property",
            explanation="Required for dynamic programming.",
        )
        # Item 3 on Graph: Student gets correct (100% accuracy -> MASTERED)
        item3 = QuizItem(
            source_id=src.id,
            concept_id=concept_graph.id,
            type=QuizItemType.MCQ,
            question="What is Dijkstra's algorithm?",
            options=["Shortest path", "Sort", "MST", "Search"],
            answer="Shortest path",
            explanation="Finds shortest path in non-negative weighted graphs.",
        )
        session.add_all([item1, item2, item3])
        session.flush()

        att1 = QuizAttempt(quiz_item_id=item1.id, response="Sorting", is_correct=False, score=0.0)
        att2 = QuizAttempt(quiz_item_id=item2.id, response="Loop", is_correct=False, score=0.0)
        att3 = QuizAttempt(quiz_item_id=item3.id, response="Shortest path", is_correct=True, score=1.0)
        session.add_all([att1, att2, att3])

    # Call API endpoint
    res = client.get("/api/v1/knowledge-gap/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["total_evaluated_topics"] >= 2
    assert data["critical_gaps_count"] >= 1

    # Check DP topic
    dp_topic = next((t for t in data["topics"] if "Dynamic Programming" in t["topic_name"]), None)
    assert dp_topic is not None
    assert dp_topic["status"] == "CRITICAL"
    assert dp_topic["accuracy_pct"] == 0.0
    assert len(dp_topic["evidence"]) == 2
    assert dp_topic["evidence"][0]["user_answer"] == "Sorting"

    # Check Graph topic
    graph_topic = next((t for t in data["topics"] if "Graph Theory" in t["topic_name"]), None)
    assert graph_topic is not None
    assert graph_topic["status"] == "MASTERED"
    assert graph_topic["accuracy_pct"] == 100.0


# =========================================================================
# 3. ADAPTIVE REVISION PLANNER TESTS
# =========================================================================

def test_revision_planner_workflow(client: TestClient):
    with session_scope() as session:
        src = Source(title="Operating Systems", kind=SourceKind.PDF, origin=SourceOrigin.UPLOAD)
        session.add(src)
        session.flush()

        # Add card due in past
        card = Card(
            source_id=src.id,
            front="What is a mutex?",
            back="Mutual exclusion primitive.",
            due=utcnow() - dt.timedelta(days=1),
        )
        session.add(card)

    # 1. Fetch recommendations
    rec_res = client.get("/api/v1/revision-planner/recommendations")
    assert rec_res.status_code == 200
    recs = rec_res.json()
    assert len(recs) > 0

    # 2. Schedule a session
    sched_res = client.post(
        "/api/v1/revision-planner/schedule",
        json={
            "topic": "Concurrency & Mutex Review",
            "priority": "HIGH",
            "recommended_duration_min": 25,
            "reason": "1 card due under FSRS.",
        },
    )
    assert sched_res.status_code == 201
    session_data = sched_res.json()
    assert session_data["status"] == "PENDING"
    assert session_data["topic"] == "Concurrency & Mutex Review"
    session_id = session_data["id"]

    # 3. List sessions
    list_res = client.get("/api/v1/revision-planner/sessions")
    assert list_res.status_code == 200
    assert any(s["id"] == session_id for s in list_res.json())

    # 4. Complete the session
    patch_res = client.patch(
        f"/api/v1/revision-planner/sessions/{session_id}",
        json={"status": "COMPLETED", "notes": "Reviewed race conditions and deadlock conditions."},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "COMPLETED"
    assert patch_res.json()["completed_at"] is not None

    # 5. Delete session
    del_res = client.delete(f"/api/v1/revision-planner/sessions/{session_id}")
    assert del_res.status_code == 200


# =========================================================================
# 4. STUDENT DASHBOARD ANALYTICS TESTS
# =========================================================================

def test_dashboard_stats_endpoint(client: TestClient):
    res = client.get("/api/v1/dashboard/stats")
    assert res.status_code == 200
    stats = res.json()
    assert "total_sources" in stats
    assert "total_cards" in stats
    assert "cards_due_today" in stats
    assert "cards_mastered" in stats
    assert "total_quiz_attempts" in stats
    assert "average_quiz_accuracy" in stats
    assert "critical_gaps_count" in stats
    assert "recent_activities" in stats
