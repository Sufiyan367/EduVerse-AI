"""Regression Tests for Truthful Metrics, Guided Learning Journey, and Course Scoping.

Verifies:
1. Truthful Course Readiness calculation:
   - Empty state returns readiness_percentage = None ("Not enough data").
   - Partial topic assessment correctly applies the 50/50 formula.
   - Exam simulation inclusion correctly applies the 40/40/20 formula.
2. Topic Learning Lifecycle:
   - Initial state is "not_started".
   - Start guided session transitions to "learning".
   - Grounded explanation returns definitions, worked examples, and evidence notes.
   - 3-question knowledge check generation and answer evaluation.
   - Successful completion (>= 80%) promotes topic to "mastered".
   - Poor performance (< 70%) marks topic as "needs_review".
   - Revision task scheduling creates a persistent task.
3. Strict multi-tenant isolation:
   - User B cannot access User A's course progress or topic learning journey.
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from quicklearn.main import create_app
from quicklearn.auth import create_access_token
from quicklearn.db.bootstrap import init_database
from quicklearn.db.enums import SourceKind, SourceOrigin, SourceStatus
from quicklearn.db.models import Base, Source, ActivityLog, User
from quicklearn.db.academic_models import (
    Course,
    CourseMaterialLink,
    CourseUnit,
    ExamSession,
    RevisionPlan,
    RevisionTask,
    StudentTopicMastery,
    SyllabusTopic,
    TopicMasteryEvent,
)
from quicklearn.db.session import session_scope


@pytest.fixture(scope="module")
def app_client():
    init_database()
    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def seeded_users():
    with session_scope() as session:
        u1 = session.query(User).filter_by(email="learner1@eduverse.ai").first()
        if not u1:
            u1 = User(
                email="learner1@eduverse.ai",
                username="learner1",
                full_name="Learner One",
                hashed_password="hashed_pw_test",
            )
            session.add(u1)
            session.flush()

        u2 = session.query(User).filter_by(email="learner2@eduverse.ai").first()
        if not u2:
            u2 = User(
                email="learner2@eduverse.ai",
                username="learner2",
                full_name="Learner Two",
                hashed_password="hashed_pw_test",
            )
            session.add(u2)
            session.flush()

        token1 = create_access_token(u1.id, u1.username, u1.email)
        token2 = create_access_token(u2.id, u2.username, u2.email)
        return {
            "u1_id": u1.id,
            "u2_id": u2.id,
            "token1": token1,
            "token2": token2,
        }


def test_empty_course_readiness_insufficient_data(app_client, seeded_users):
    """Empty course or course with 0 assessments returns None readiness and clear calculation basis."""
    token1 = seeded_users["token1"]
    headers = {"Authorization": f"Bearer {token1}"}

    res = app_client.post(
        "/api/v1/courses",
        headers=headers,
        json={
            "code": "TEST101_EMPTY",
            "name": "Intro to Testing",
            "semester": "Semester 1",
            "academic_year": "2025-2026",
            "description": "Empty test course",
        },
    )
    assert res.status_code in (200, 201)
    course_id = res.json()["id"]

    prog_res = app_client.get(f"/api/v1/courses/{course_id}/progress", headers=headers)
    assert prog_res.status_code == 200
    data = prog_res.json()

    assert data["readiness_percentage"] is None
    assert data["has_sufficient_data"] is False
    assert "Not enough data" in data["calculation_basis"]
    assert data["total_topics"] == 0
    assert data["assessed_topics_count"] == 0


def test_partial_assessment_readiness_formula(app_client, seeded_users):
    """Course with 4 topics and 2 assessed topics computes formula 50/50 exactly."""
    token1 = seeded_users["token1"]
    u1_id = seeded_users["u1_id"]
    headers = {"Authorization": f"Bearer {token1}"}

    c_res = app_client.post(
        "/api/v1/courses",
        headers=headers,
        json={
            "code": "CS302_PARTIAL",
            "name": "Operating Systems Partial",
            "semester": "Semester 3",
            "academic_year": "2025-2026",
            "description": "OS Principles",
        },
    )
    assert c_res.status_code in (200, 201)
    course_id = c_res.json()["id"]

    with session_scope() as session:
        unit = CourseUnit(
            course_id=course_id,
            unit_number=1,
            title="Unit 1: Process Scheduling",
        )
        session.add(unit)
        session.flush()

        t1 = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Round Robin Scheduling")
        t2 = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Priority Inversion")
        t3 = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Deadlock Detection")
        t4 = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Banker's Algorithm")
        session.add_all([t1, t2, t3, t4])
        session.flush()

        m1 = StudentTopicMastery(
            user_id=u1_id,
            topic_id=t1.id,
            mastery_score=0.8,
            confidence_level="high",
            status="mastered",
        )
        m2 = StudentTopicMastery(
            user_id=u1_id,
            topic_id=t2.id,
            mastery_score=0.6,
            confidence_level="medium",
            status="learning",
        )
        session.add_all([m1, m2])

    prog_res = app_client.get(f"/api/v1/courses/{course_id}/progress", headers=headers)
    assert prog_res.status_code == 200
    data = prog_res.json()

    assert data["total_topics"] == 4
    assert data["assessed_topics_count"] == 2
    # Coverage: 2/4 = 0.5
    # Avg mastery: (0.8 + 0.6) / 2 = 0.7
    # Readiness = 0.5 * 0.5 + 0.5 * 0.7 = 0.25 + 0.35 = 0.60 -> 60.0%
    assert data["readiness_percentage"] == 60.0
    assert (data["assessed_topics_count"] / data["total_topics"]) == 0.5
    assert data["average_topic_mastery"] == 0.7
    assert data["topics_by_status"]["mastered"] == 1
    assert data["topics_by_status"]["learning"] == 1
    assert data["topics_by_status"]["not_started"] == 2


def test_exam_simulation_readiness_formula(app_client, seeded_users):
    """When exam session attempt exists, 40/40/20 formula is used."""
    token1 = seeded_users["token1"]
    u1_id = seeded_users["u1_id"]
    headers = {"Authorization": f"Bearer {token1}"}

    c_res = app_client.post(
        "/api/v1/courses",
        headers=headers,
        json={
            "code": "CS302_EXAM",
            "name": "Operating Systems Exam Grounded",
            "semester": "Semester 3",
            "academic_year": "2025-2026",
            "description": "OS Principles with Exam",
        },
    )
    assert c_res.status_code in (200, 201)
    course_id = c_res.json()["id"]

    with session_scope() as session:
        unit = CourseUnit(
            course_id=course_id,
            unit_number=1,
            title="Unit 1: Process Scheduling",
        )
        session.add(unit)
        session.flush()

        t1 = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Round Robin Scheduling")
        t2 = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Priority Inversion")
        t3 = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Deadlock Detection")
        t4 = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Banker's Algorithm")
        session.add_all([t1, t2, t3, t4])
        session.flush()

        m1 = StudentTopicMastery(
            user_id=u1_id,
            topic_id=t1.id,
            mastery_score=0.8,
            confidence_level="high",
            status="mastered",
        )
        m2 = StudentTopicMastery(
            user_id=u1_id,
            topic_id=t2.id,
            mastery_score=0.6,
            confidence_level="medium",
            status="learning",
        )
        session.add_all([m1, m2])

        # 45/50 = 90%
        attempt = ExamSession(
            course_id=course_id,
            user_id=u1_id,
            title="Mid-Term Simulation",
            status="graded",
            total_score=45.0,
            max_score=50.0,
        )
        session.add(attempt)

    prog_res = app_client.get(f"/api/v1/courses/{course_id}/progress", headers=headers)
    assert prog_res.status_code == 200
    data = prog_res.json()

    assert data["exam_attempts_count"] == 1
    assert data["average_exam_score"] == 90.0
    # Formula: 0.4 * 0.5 (coverage) + 0.4 * 0.7 (mastery) + 0.2 * (90/100)
    # = 0.20 + 0.28 + 0.18 = 0.66 -> 66.0%
    assert data["readiness_percentage"] == 66.0


def test_topic_learning_lifecycle_flow(app_client, seeded_users):
    """Verify topic lifecycle: not_started -> learning -> quiz -> mastered / needs_review."""
    token1 = seeded_users["token1"]
    u1_id = seeded_users["u1_id"]
    headers = {"Authorization": f"Bearer {token1}"}

    c_res = app_client.post(
        "/api/v1/courses",
        headers=headers,
        json={
            "code": "CS302_FLOW",
            "name": "Operating Systems Guided Flow",
            "semester": "Semester 3",
            "academic_year": "2025-2026",
            "description": "Guided Learning Lifecycle",
        },
    )
    assert c_res.status_code in (200, 201)
    course_id = c_res.json()["id"]

    with session_scope() as session:
        unit = CourseUnit(course_id=course_id, unit_number=1, title="Unit 1")
        session.add(unit)
        session.flush()
        topic = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Deadlock Detection")
        session.add(topic)
        session.flush()
        topic_id = topic.id

    # 1. GET learning context
    get_res = app_client.get(f"/api/v1/courses/{course_id}/topics/{topic_id}/learning", headers=headers)
    assert get_res.status_code == 200
    ctx = get_res.json()
    assert ctx["topic"]["id"] == topic_id
    assert ctx["topic"]["name"] == "Deadlock Detection"
    assert ctx["lifecycle"]["status"] == "not_started"
    assert len(ctx["learning_objectives"]) >= 1
    assert "recommended_action" in ctx

    # 2. START learning
    start_res = app_client.post(f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/start", headers=headers)
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "learning"

    # 3. EXPLAIN topic
    explain_res = app_client.post(
        f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/explain?mode=standard",
        headers=headers,
    )
    assert explain_res.status_code == 200
    exp = explain_res.json()
    assert "summary" in exp
    assert len(exp["definitions"]) >= 1
    assert "worked_example" in exp
    assert "disclaimer" in exp

    # 4. GET 3-question knowledge check
    quiz_res = app_client.post(f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/quiz", headers=headers)
    assert quiz_res.status_code == 200
    q_data = quiz_res.json()
    assert len(q_data["questions"]) == 3
    q1 = q_data["questions"][0]
    assert len(q1["options"]) >= 2

    # 5. SUBMIT passing answers (all correct)
    answers_payload = [
        {"question_id": q["id"], "selected_option": q["correct_option"]}
        for q in q_data["questions"]
    ]
    sub_res = app_client.post(
        f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/submit",
        headers=headers,
        json={"answers": answers_payload},
    )
    assert sub_res.status_code == 200
    res_data = sub_res.json()
    assert res_data["score"] == 1.0
    assert res_data["correct_count"] == 3
    assert res_data["new_status"] == "mastered"
    assert res_data["passed"] is True

    # 6. Verify DB record transitioned and activity logged
    with session_scope() as session:
        mastery = session.query(StudentTopicMastery).filter_by(user_id=u1_id, topic_id=topic_id).first()
        assert mastery is not None
        assert mastery.status == "mastered"
        assert mastery.mastery_score == 1.0

        activity = session.query(ActivityLog).filter_by(user_id=u1_id, action="complete_knowledge_check").first()
        assert activity is not None

        event = session.query(TopicMasteryEvent).filter_by(user_id=u1_id, topic_id=topic_id).first()
        assert event is not None


def test_submit_failing_quiz_sets_needs_review(app_client, seeded_users):
    """Submitting score < 70% sets topic to needs_review."""
    token1 = seeded_users["token1"]
    u1_id = seeded_users["u1_id"]
    headers = {"Authorization": f"Bearer {token1}"}

    c_res = app_client.post(
        "/api/v1/courses",
        headers=headers,
        json={
            "code": "CS302_FAIL",
            "name": "Operating Systems Fail Case",
            "semester": "Semester 3",
            "academic_year": "2025-2026",
            "description": "Failing quiz test",
        },
    )
    assert c_res.status_code in (200, 201)
    course_id = c_res.json()["id"]

    with session_scope() as session:
        unit = CourseUnit(course_id=course_id, unit_number=1, title="Unit 1")
        session.add(unit)
        session.flush()
        topic = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Banker's Algorithm")
        session.add(topic)
        session.flush()
        topic_id = topic.id

    # Start learning
    app_client.post(f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/start", headers=headers)

    # Submit intentionally wrong answers
    sub_res = app_client.post(
        f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/submit",
        headers=headers,
        json={"answers": [
            {"question_id": 1, "selected_option": "Z"},
            {"question_id": 2, "selected_option": "Z"},
            {"question_id": 3, "selected_option": "Z"},
        ]},
    )
    assert sub_res.status_code == 200
    res_data = sub_res.json()
    assert res_data["score"] < 0.7
    assert res_data["new_status"] == "needs_review"
    assert len(res_data["mistakes"]) >= 1


def test_schedule_topic_revision_creates_task(app_client, seeded_users):
    """Scheduling revision creates a persistent RevisionTask for that topic."""
    token1 = seeded_users["token1"]
    u1_id = seeded_users["u1_id"]
    headers = {"Authorization": f"Bearer {token1}"}

    c_res = app_client.post(
        "/api/v1/courses",
        headers=headers,
        json={
            "code": "CS302_REV",
            "name": "Operating Systems Revision Case",
            "semester": "Semester 3",
            "academic_year": "2025-2026",
            "description": "Revision task test",
        },
    )
    assert c_res.status_code in (200, 201)
    course_id = c_res.json()["id"]

    with session_scope() as session:
        unit = CourseUnit(course_id=course_id, unit_number=1, title="Unit 1")
        session.add(unit)
        session.flush()
        topic = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Memory Fragmentation")
        session.add(topic)
        session.flush()
        topic_id = topic.id

    rev_res = app_client.post(
        f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/revision",
        headers=headers,
    )
    assert rev_res.status_code == 200
    data = rev_res.json()
    assert data["scheduled"] is True
    assert data["topic_id"] == topic_id
    assert "priority" in data

    with session_scope() as session:
        task = session.query(RevisionTask).filter_by(topic_id=topic_id).first()
        assert task is not None


def test_user_isolation_blocks_cross_tenant_access(app_client, seeded_users):
    """User 2 cannot view or mutate User 1's courses or topic learning journeys."""
    token1 = seeded_users["token1"]
    token2 = seeded_users["token2"]
    u1_id = seeded_users["u1_id"]

    c_res = app_client.post(
        "/api/v1/courses",
        headers={"Authorization": f"Bearer {token1}"},
        json={
            "code": "CS302_ISO",
            "name": "Operating Systems Isolation Case",
            "semester": "Semester 3",
            "academic_year": "2025-2026",
            "description": "Multi-tenant isolation test",
        },
    )
    assert c_res.status_code in (200, 201)
    course_id = c_res.json()["id"]

    with session_scope() as session:
        unit = CourseUnit(course_id=course_id, unit_number=1, title="Unit 1")
        session.add(unit)
        session.flush()
        topic = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Isolated Topic")
        session.add(topic)
        session.flush()
        topic_id = topic.id

    # User 2 tries to access User 1's course progress
    res_prog = app_client.get(
        f"/api/v1/courses/{course_id}/progress",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert res_prog.status_code == 404

    # User 2 tries to access User 1's topic learning journey
    res_learn = app_client.get(
        f"/api/v1/courses/{course_id}/topics/{topic_id}/learning",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert res_learn.status_code == 404

    # User 2 tries to submit quiz for User 1's topic
    res_sub = app_client.post(
        f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/submit",
        headers={"Authorization": f"Bearer {token2}"},
        json={"answers": [{"question_id": 1, "selected_option": "A"}]},
    )
    assert res_sub.status_code == 404
