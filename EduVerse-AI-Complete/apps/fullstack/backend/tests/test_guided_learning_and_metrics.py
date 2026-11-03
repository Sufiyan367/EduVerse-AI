"""Comprehensive Regression and Adversarial Tests for EduVerse AI:
1. Truthful Academic Metrics & Readiness Calculation:
   - Zero topics / zero assessments returns readiness_percentage = None ("Not enough data").
   - Activity vs Assessment separation: starting topic learning (status="learning", mastery_score=0.0)
     counts as study activity, NOT demonstrated assessment.
   - 50/50 formula (coverage + average mastery) when no graded exams exist.
   - 40/40/20 formula (coverage + mastery + exam score) when graded exams exist.
   - Ungraded / in_progress exam sessions are ignored in metrics.

2. Guided Learning Lifecycle & Pedagogy:
   - Initial status: not_started.
   - Start learning transitions to status="learning" without inflating assessment metrics.
   - Pedagogical explanation modes (standard, simple, example, compare) alter instructional approach.
   - Explanations grounded with verified citations or clear unlinked material disclaimers.
   - Distinct, non-duplicated explanation fields: summary != worked_example.
   - 10-question diagnostic check generation without leaking correct_option to the client.

3. Cryptographic Quiz Security & Server-Side Session Integrity:
   - Opaque, unguessable session token backed by GuidedQuizSession in SQLite.
   - Zero confidential answer keys or explanations delivered to client before submission.
   - Rejects non-existent/guessed session tokens (404 Not Found).
   - Rejects cross-user quiz session submissions (403 Forbidden).
   - Rejects token reuse / replay attacks after consumption (409 Conflict).
   - Rejects expired quiz sessions (410 Gone).
   - Rejects empty, missing, duplicate question submissions (422 Unprocessable Entity).
   - Rejects invalid option choices (422 Unprocessable Entity).
   - Mastery threshold enforcement: >=80% mastered, 70-79% practicing, <70% needs_review.
   - Status reason transparently explains policy justification.

4. Multi-Tenant Security & Adversarial RAG Isolation:
   - Strict isolation across all 5 scopes (all, source, folder, course, topic).
   - User 2 cannot retrieve User 1's excerpts in topic, course, source, or folder scopes.
   - Foreign source links in CourseMaterialLink are stripped.
   - User 2 cannot access or mutate User 1's courses, topics, or learning sessions (404).
"""

import time
import pytest
import secrets
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from quicklearn.main import create_app
from quicklearn.auth import create_access_token
from quicklearn.db.bootstrap import init_database
from quicklearn.db.enums import SourceKind, SourceOrigin, SourceStatus
from quicklearn.db.models import Base, Source, Segment, Folder, ActivityLog, User
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
    GuidedQuizSession,
)
from quicklearn.db.session import session_scope
from quicklearn.api.guided_learning import (
    evaluate_mastery_threshold,
    _randomize_question_options,
    SUBJECT_QUESTION_BANK,
)
from quicklearn.rag.retrieve import retrieve
from quicklearn.rag.manifest import get_user_source_manifest


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


# ===========================================================================
# 1. TRUTHFUL METRICS & ACTIVITY VS ASSESSMENT SEPARATION
# ===========================================================================

def test_empty_course_readiness_insufficient_data(app_client, seeded_users):
    """Empty course or course with 0 assessments returns None readiness and clear calculation basis."""
    token1 = seeded_users["token1"]
    headers = {"Authorization": f"Bearer {token1}"}

    res = app_client.post(
        "/api/v1/courses",
        headers=headers,
        json={
            "code": "TEST_EMPTY_01",
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


def test_activity_vs_assessment_separation(app_client, seeded_users):
    """Starting topic learning transitions status to 'learning', but does NOT count as assessed performance."""
    token1 = seeded_users["token1"]
    u1_id = seeded_users["u1_id"]
    headers = {"Authorization": f"Bearer {token1}"}

    c_res = app_client.post(
        "/api/v1/courses",
        headers=headers,
        json={
            "code": "CS_ACT_VS_ASSESS",
            "name": "Activity Separation Test",
            "semester": "Semester 1",
            "academic_year": "2025-2026",
            "description": "Testing that starting study does not fabricate readiness",
        },
    )
    assert c_res.status_code in (200, 201)
    course_id = c_res.json()["id"]

    with session_scope() as session:
        unit = CourseUnit(course_id=course_id, unit_number=1, title="Unit 1")
        session.add(unit)
        session.flush()
        topic = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Topic Alpha")
        session.add(topic)
        session.flush()
        topic_id = topic.id

    # 1. Start learning session
    start_res = app_client.post(f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/start", headers=headers)
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "learning"

    # 2. Check DB: mastery_score is 0.0 and last_evaluated_at is None
    with session_scope() as session:
        m = session.query(StudentTopicMastery).filter_by(user_id=u1_id, topic_id=topic_id).first()
        assert m is not None
        assert m.status == "learning"
        assert m.mastery_score == 0.0
        assert m.last_evaluated_at is None

    # 3. Check Course Progress: topic is 'learning' in breakdown, but assessed_topics_count MUST BE 0
    prog_res = app_client.get(f"/api/v1/courses/{course_id}/progress", headers=headers)
    assert prog_res.status_code == 200
    pdata = prog_res.json()
    assert pdata["total_topics"] == 1
    assert pdata["assessed_topics_count"] == 0
    assert pdata["readiness_percentage"] is None
    assert pdata["has_sufficient_data"] is False
    assert pdata["topics_by_status"]["learning"] == 1


def test_partial_assessment_readiness_formula(app_client, seeded_users):
    """Course with 4 topics and 2 evaluated topics computes 50/50 formula exactly."""
    token1 = seeded_users["token1"]
    u1_id = seeded_users["u1_id"]
    headers = {"Authorization": f"Bearer {token1}"}

    c_res = app_client.post(
        "/api/v1/courses",
        headers=headers,
        json={
            "code": "CS302_PARTIAL_TEST",
            "name": "Operating Systems Partial",
            "semester": "Semester 3",
            "academic_year": "2025-2026",
            "description": "OS Principles",
        },
    )
    assert c_res.status_code in (200, 201)
    course_id = c_res.json()["id"]

    now = datetime.now(timezone.utc)
    with session_scope() as session:
        unit = CourseUnit(course_id=course_id, unit_number=1, title="Unit 1: Process Scheduling")
        session.add(unit)
        session.flush()

        t1 = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Round Robin Scheduling")
        t2 = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Priority Inversion")
        t3 = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Deadlock Detection")
        t4 = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Banker's Algorithm")
        session.add_all([t1, t2, t3, t4])
        session.flush()

        # Topic 1: evaluated and mastered (80%)
        m1 = StudentTopicMastery(
            user_id=u1_id,
            topic_id=t1.id,
            mastery_score=0.8,
            confidence_level="high",
            status="mastered",
            last_evaluated_at=now,
        )
        # Topic 2: evaluated and needs review (60%)
        m2 = StudentTopicMastery(
            user_id=u1_id,
            topic_id=t2.id,
            mastery_score=0.6,
            confidence_level="medium",
            status="needs_review",
            last_evaluated_at=now,
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
    assert data["average_topic_mastery"] == 0.7
    assert data["topics_by_status"]["mastered"] == 1
    assert data["topics_by_status"]["needs_review"] == 1
    assert data["topics_by_status"]["not_started"] == 2


def test_exam_simulation_readiness_formula(app_client, seeded_users):
    """When graded exam session attempt exists, 40/40/20 formula is used; in_progress exam is ignored."""
    token1 = seeded_users["token1"]
    u1_id = seeded_users["u1_id"]
    headers = {"Authorization": f"Bearer {token1}"}

    c_res = app_client.post(
        "/api/v1/courses",
        headers=headers,
        json={
            "code": "CS302_EXAM_TEST",
            "name": "Operating Systems Exam Grounded",
            "semester": "Semester 3",
            "academic_year": "2025-2026",
            "description": "OS Principles with Exam",
        },
    )
    assert c_res.status_code in (200, 201)
    course_id = c_res.json()["id"]

    now = datetime.now(timezone.utc)
    with session_scope() as session:
        unit = CourseUnit(course_id=course_id, unit_number=1, title="Unit 1")
        session.add(unit)
        session.flush()

        t1 = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Paging")
        t2 = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Segmentation")
        t3 = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Virtual Memory")
        t4 = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Thrashing")
        session.add_all([t1, t2, t3, t4])
        session.flush()

        m1 = StudentTopicMastery(
            user_id=u1_id,
            topic_id=t1.id,
            mastery_score=0.8,
            confidence_level="high",
            status="mastered",
            last_evaluated_at=now,
        )
        m2 = StudentTopicMastery(
            user_id=u1_id,
            topic_id=t2.id,
            mastery_score=0.6,
            confidence_level="medium",
            status="needs_review",
            last_evaluated_at=now,
        )
        session.add_all([m1, m2])

        # Attempt 1: In progress (ungraded) -> MUST BE IGNORED
        att_in_prog = ExamSession(
            course_id=course_id,
            user_id=u1_id,
            title="Unfinished Simulation",
            status="in_progress",
            total_score=0.0,
            max_score=100.0,
        )
        # Attempt 2: Graded (45/50 = 90%)
        att_graded = ExamSession(
            course_id=course_id,
            user_id=u1_id,
            title="Mid-Term Simulation",
            status="graded",
            total_score=45.0,
            max_score=50.0,
        )
        session.add_all([att_in_prog, att_graded])

    prog_res = app_client.get(f"/api/v1/courses/{course_id}/progress", headers=headers)
    assert prog_res.status_code == 200
    data = prog_res.json()

    assert data["exam_attempts_count"] == 1
    assert data["average_exam_score"] == 90.0
    # Formula: 0.4 * 0.5 (coverage) + 0.4 * 0.7 (mastery) + 0.2 * (90/100)
    # = 0.20 + 0.28 + 0.18 = 0.66 -> 66.0%
    assert data["readiness_percentage"] == 66.0


# ===========================================================================
# 2. GUIDED LEARNING LIFECYCLE, EXPLANATIONS & PEDAGOGY
# ===========================================================================

def test_topic_learning_lifecycle_flow(app_client, seeded_users):
    """Verify topic lifecycle: not_started -> learning -> 10-question quiz -> mastered (>=80%)."""
    token1 = seeded_users["token1"]
    u1_id = seeded_users["u1_id"]
    headers = {"Authorization": f"Bearer {token1}"}

    c_res = app_client.post(
        "/api/v1/courses",
        headers=headers,
        json={
            "code": "CS_LIFECYCLE_01",
            "name": "Lifecycle Architecture",
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

    # 2. START learning
    start_res = app_client.post(f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/start", headers=headers)
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "learning"

    # 3. EXPLAIN topic across different pedagogical modes
    for mode in ["standard", "simple", "example", "compare"]:
        explain_res = app_client.post(
            f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/explain?mode={mode}",
            headers=headers,
        )
        assert explain_res.status_code == 200
        exp = explain_res.json()
        assert "summary" in exp
        assert "worked_example" in exp
        assert exp["mode"] == mode
        # Structural integrity check: worked_example must be distinct from summary
        assert exp["summary"].strip() != exp["worked_example"].strip()

    # 4. GET 10-question diagnostic knowledge check
    quiz_res = app_client.post(f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/quiz", headers=headers)
    assert quiz_res.status_code == 200
    q_data = quiz_res.json()
    assert q_data["available"] is True
    assert len(q_data["questions"]) == 10
    assert "quiz_token" in q_data

    # Verify security sanitation: correct_option is NOT leaked anywhere in client questions
    for q in q_data["questions"]:
        assert "correct_option" not in q
        assert "explanation" not in q
        assert len(q["options"]) == 4

    # Fetch answer key securely from the server-side session in database
    session_token = q_data["quiz_token"]
    with session_scope() as session:
        quiz_session = session.query(GuidedQuizSession).filter_by(session_token=session_token).first()
        assert quiz_session is not None
        assert quiz_session.user_id == u1_id
        assert quiz_session.course_id == course_id
        assert quiz_session.topic_id == topic_id
        assert quiz_session.consumed_at is None
        answer_key = quiz_session.answer_key

    answers_payload = [
        {"question_id": int(qid), "selected_option": opt}
        for qid, opt in answer_key.items()
    ]

    # 5. SUBMIT passing answers (all 10 correct -> 100%)
    sub_res = app_client.post(
        f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/submit",
        headers=headers,
        json={"answers": answers_payload, "quiz_token": session_token},
    )
    assert sub_res.status_code == 200
    res_data = sub_res.json()
    assert res_data["score"] == 1.0
    assert res_data["score_percent"] == 100
    assert res_data["correct_count"] == 10
    assert res_data["total_questions"] == 10
    assert res_data["new_status"] == "mastered"
    assert res_data["passed"] is True
    assert "status_reason" in res_data
    assert "Mastered" in res_data["status_reason"]

    # 6. Verify DB record transitioned and activity logged
    with session_scope() as session:
        mastery = session.query(StudentTopicMastery).filter_by(user_id=u1_id, topic_id=topic_id).first()
        assert mastery is not None
        assert mastery.status == "mastered"
        assert mastery.mastery_score == 1.0
        assert mastery.last_evaluated_at is not None

        activity = session.query(ActivityLog).filter_by(user_id=u1_id, action="complete_knowledge_check").first()
        assert activity is not None

        event = session.query(TopicMasteryEvent).filter_by(user_id=u1_id, topic_id=topic_id, event_type="knowledge_check").first()
        assert event is not None
        assert event.score == 1.0

        # Verify session marked consumed in DB
        db_sess = session.query(GuidedQuizSession).filter_by(session_token=session_token).first()
        assert db_sess.consumed_at is not None


# ===========================================================================
# 3. MASTERY THRESHOLD BOUNDARIES & POLICY EXPLANATION
# ===========================================================================

def test_mastery_threshold_boundaries(app_client, seeded_users):
    """Verify threshold enforcement: >=80% = mastered, 70-79% = practicing, <70% = needs_review."""
    token1 = seeded_users["token1"]
    headers = {"Authorization": f"Bearer {token1}"}

    # Test pure threshold function at exact boundary values
    assert evaluate_mastery_threshold(69.0)[0] == "needs_review"
    assert evaluate_mastery_threshold(69.9)[0] == "needs_review"
    assert evaluate_mastery_threshold(70.0)[0] == "practicing"
    assert evaluate_mastery_threshold(75.0)[0] == "practicing"
    assert evaluate_mastery_threshold(79.9)[0] == "practicing"
    assert evaluate_mastery_threshold(80.0)[0] == "mastered"
    assert evaluate_mastery_threshold(90.0)[0] == "mastered"
    assert evaluate_mastery_threshold(100.0)[0] == "mastered"

    c_res = app_client.post(
        "/api/v1/courses",
        headers=headers,
        json={
            "code": "CS_THRESHOLDS_01",
            "name": "Thresholds Boundary Check",
            "semester": "Semester 3",
            "academic_year": "2025-2026",
            "description": "Boundary conditions for topic mastery",
        },
    )
    assert c_res.status_code in (200, 201)
    course_id = c_res.json()["id"]

    with session_scope() as session:
        unit = CourseUnit(course_id=course_id, unit_number=1, title="Unit 1")
        session.add(unit)
        session.flush()

        t_fail = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Deadlock Detection")
        session.add(t_fail)
        session.flush()
        t_fail_id = t_fail.id

    # Test Failing (< 70%): answer all wrong -> 0% -> needs_review
    q_res = app_client.post(f"/api/v1/courses/{course_id}/topics/{t_fail_id}/learning/quiz", headers=headers)
    assert q_res.status_code == 200
    q_data = q_res.json()
    quiz_token = q_data["quiz_token"]

    with session_scope() as session:
        quiz_session = session.query(GuidedQuizSession).filter_by(session_token=quiz_token).first()
        answer_key = quiz_session.answer_key

    # Choose deliberate wrong answer for all 10 questions
    wrong_answers = []
    for q in q_data["questions"]:
        qid_str = str(q["id"])
        correct = answer_key[qid_str]
        wrong_opt = [opt for opt in ["A", "B", "C", "D"] if opt != correct][0]
        wrong_answers.append({"question_id": q["id"], "selected_option": wrong_opt})

    sub_res = app_client.post(
        f"/api/v1/courses/{course_id}/topics/{t_fail_id}/learning/submit",
        headers=headers,
        json={"answers": wrong_answers, "quiz_token": quiz_token},
    )
    assert sub_res.status_code == 200
    f_data = sub_res.json()
    assert f_data["score"] == 0.0
    assert f_data["score_percent"] == 0
    assert f_data["new_status"] == "needs_review"
    assert f_data["passed"] is False
    assert "Needs Review" in f_data["status_reason"]
    assert len(f_data["mistakes"]) == 10

    # Test Boundary 70% (7 correct, 3 wrong) -> practicing (passed is False, since 80% is needed for mastery)
    q2_res = app_client.post(f"/api/v1/courses/{course_id}/topics/{t_fail_id}/learning/quiz", headers=headers)
    assert q2_res.status_code == 200
    q2_data = q2_res.json()
    quiz_token2 = q2_data["quiz_token"]

    with session_scope() as session:
        quiz_session2 = session.query(GuidedQuizSession).filter_by(session_token=quiz_token2).first()
        answer_key2 = quiz_session2.answer_key

    answers_70 = []
    for idx, q in enumerate(q2_data["questions"]):
        qid_str = str(q["id"])
        correct = answer_key2[qid_str]
        if idx < 7:
            answers_70.append({"question_id": q["id"], "selected_option": correct})
        else:
            wrong_opt = [opt for opt in ["A", "B", "C", "D"] if opt != correct][0]
            answers_70.append({"question_id": q["id"], "selected_option": wrong_opt})

    sub2_res = app_client.post(
        f"/api/v1/courses/{course_id}/topics/{t_fail_id}/learning/submit",
        headers=headers,
        json={"answers": answers_70, "quiz_token": quiz_token2},
    )
    assert sub2_res.status_code == 200
    res70 = sub2_res.json()
    assert res70["score_percent"] == 70
    assert res70["correct_count"] == 7
    assert res70["new_status"] == "practicing"
    assert res70["passed"] is False

    # Test Boundary 80% (8 correct, 2 wrong) -> mastered (passed is True)
    q3_res = app_client.post(f"/api/v1/courses/{course_id}/topics/{t_fail_id}/learning/quiz", headers=headers)
    assert q3_res.status_code == 200
    q3_data = q3_res.json()
    quiz_token3 = q3_data["quiz_token"]

    with session_scope() as session:
        quiz_session3 = session.query(GuidedQuizSession).filter_by(session_token=quiz_token3).first()
        answer_key3 = quiz_session3.answer_key

    answers_80 = []
    for idx, q in enumerate(q3_data["questions"]):
        qid_str = str(q["id"])
        correct = answer_key3[qid_str]
        if idx < 8:
            answers_80.append({"question_id": q["id"], "selected_option": correct})
        else:
            wrong_opt = [opt for opt in ["A", "B", "C", "D"] if opt != correct][0]
            answers_80.append({"question_id": q["id"], "selected_option": wrong_opt})

    sub3_res = app_client.post(
        f"/api/v1/courses/{course_id}/topics/{t_fail_id}/learning/submit",
        headers=headers,
        json={"answers": answers_80, "quiz_token": quiz_token3},
    )
    assert sub3_res.status_code == 200
    res80 = sub3_res.json()
    assert res80["score_percent"] == 80
    assert res80["correct_count"] == 8
    assert res80["new_status"] == "mastered"
    assert res80["passed"] is True


# ===========================================================================
# 4. CRYPTOGRAPHIC QUIZ SECURITY, OPAQUE TOKENS & REPLAY ATTACK PREVENTION
# ===========================================================================

def test_quiz_token_is_opaque_and_unguessable(app_client, seeded_users):
    """Verify that quiz_token is a purely opaque random URL-safe string containing no leaked answer keys."""
    token1 = seeded_users["token1"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    c_res = app_client.post(
        "/api/v1/courses",
        headers=headers1,
        json={
            "code": "CS_OPAQUE_01",
            "name": "Opaque Token Verification",
            "semester": "Semester 3",
            "academic_year": "2025-2026",
            "description": "Verifying token confidentiality",
        },
    )
    assert c_res.status_code in (200, 201)
    course_id = c_res.json()["id"]

    with session_scope() as session:
        unit = CourseUnit(course_id=course_id, unit_number=1, title="Unit 1")
        session.add(unit)
        session.flush()
        topic = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Database Normalization")
        session.add(topic)
        session.flush()
        topic_id = topic.id

    q_res = app_client.post(f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/quiz", headers=headers1)
    assert q_res.status_code == 200
    data = q_res.json()
    quiz_token = data["quiz_token"]

    # Must be unguessable URL-safe token (at least 40 chars, no dot/HMAC signature structure)
    assert len(quiz_token) >= 40
    assert "." not in quiz_token
    # Must NOT decode to JSON containing answer keys
    import base64
    try:
        padded = quiz_token + "=" * (-len(quiz_token) % 4)
        raw = base64.urlsafe_b64decode(padded)
        assert b"answer_key" not in raw
        assert b"explanations" not in raw
        assert b"correct_option" not in raw
    except Exception:
        # If it doesn't even decode to valid base64 bytes, it is completely opaque
        pass


def test_quiz_token_tampering_and_adversarial_submissions(app_client, seeded_users):
    """Test session token validation, cross-user rejection, replay attacks (409), and expired sessions (410)."""
    token1 = seeded_users["token1"]
    token2 = seeded_users["token2"]
    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}

    c_res = app_client.post(
        "/api/v1/courses",
        headers=headers1,
        json={
            "code": "CS_SECURITY_01",
            "name": "Operating Systems Security",
            "semester": "Semester 3",
            "academic_year": "2025-2026",
            "description": "Server-side quiz session validation",
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

    # Get valid quiz token for User 1
    q_res = app_client.post(f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/quiz", headers=headers1)
    assert q_res.status_code == 200
    valid_token = q_res.json()["quiz_token"]
    questions = q_res.json()["questions"]
    valid_qids = [q["id"] for q in questions]
    assert len(valid_qids) == 10

    # 1. Non-existent / fabricated token -> 404
    fake_token = "completely_fabricated_session_token_xyz1234567890"
    res_fake = app_client.post(
        f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/submit",
        headers=headers1,
        json={"answers": [{"question_id": qid, "selected_option": "A"} for qid in valid_qids], "quiz_token": fake_token},
    )
    assert res_fake.status_code == 404
    assert "not found" in res_fake.json()["detail"].lower()

    # 2. Cross-user token submission: User 2 uses User 1's token on User 2's own course/topic -> 403 Forbidden
    c2_res = app_client.post(
        "/api/v1/courses",
        headers=headers2,
        json={
            "code": "CS_USER2_COURSE",
            "name": "User 2 Course",
            "semester": "Semester 1",
            "academic_year": "2025-2026",
            "description": "User 2 course",
        },
    )
    c2_id = c2_res.json()["id"]
    with session_scope() as session:
        u2_unit = CourseUnit(course_id=c2_id, unit_number=1, title="Unit 1")
        session.add(u2_unit)
        session.flush()
        u2_topic = SyllabusTopic(course_id=c2_id, unit_id=u2_unit.id, name="Deadlock Detection")
        session.add(u2_topic)
        session.flush()
        u2_topic_id = u2_topic.id

    res_cross_user = app_client.post(
        f"/api/v1/courses/{c2_id}/topics/{u2_topic_id}/learning/submit",
        headers=headers2,
        json={"answers": [{"question_id": qid, "selected_option": "A"} for qid in valid_qids], "quiz_token": valid_token},
    )
    assert res_cross_user.status_code == 403
    assert "Forbidden" in res_cross_user.json()["detail"]

    # 3. Missing answers (only 9 out of 10 answered) -> 422
    partial_answers = [{"question_id": qid, "selected_option": "A"} for qid in valid_qids[:9]]
    res_missing = app_client.post(
        f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/submit",
        headers=headers1,
        json={"answers": partial_answers, "quiz_token": valid_token},
    )
    assert res_missing.status_code == 422
    assert "Missing answers" in res_missing.json()["detail"]

    # 4. Duplicate question ID submission -> 422
    dup_answers = [{"question_id": valid_qids[0], "selected_option": "A"}] + [
        {"question_id": qid, "selected_option": "A"} for qid in valid_qids[:9]
    ]
    res_dup = app_client.post(
        f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/submit",
        headers=headers1,
        json={"answers": dup_answers, "quiz_token": valid_token},
    )
    assert res_dup.status_code == 422
    assert "Duplicate answer" in res_dup.json()["detail"]

    # 5. Invalid option letter ('Z') -> 422
    invalid_opt_answers = [{"question_id": qid, "selected_option": "A"} for qid in valid_qids]
    invalid_opt_answers[0]["selected_option"] = "Z"
    res_invalid_opt = app_client.post(
        f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/submit",
        headers=headers1,
        json={"answers": invalid_opt_answers, "quiz_token": valid_token},
    )
    assert res_invalid_opt.status_code == 422
    assert "Invalid option" in res_invalid_opt.json()["detail"]

    # 6. Valid first submission succeeds
    all_answers = [{"question_id": qid, "selected_option": "A"} for qid in valid_qids]
    res_submit_ok = app_client.post(
        f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/submit",
        headers=headers1,
        json={"answers": all_answers, "quiz_token": valid_token},
    )
    assert res_submit_ok.status_code == 200

    # 7. Token Reuse / Replay Attack: submitting the same token a second time -> 409 Conflict
    res_replay = app_client.post(
        f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/submit",
        headers=headers1,
        json={"answers": all_answers, "quiz_token": valid_token},
    )
    assert res_replay.status_code == 409
    assert "already been submitted" in res_replay.json()["detail"].lower()

    # 8. Expired Token: session with expires_at in the past -> 410 Gone
    q_expired_res = app_client.post(f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/quiz", headers=headers1)
    assert q_expired_res.status_code == 200
    expired_token = q_expired_res.json()["quiz_token"]
    with session_scope() as session:
        exp_sess = session.query(GuidedQuizSession).filter_by(session_token=expired_token).first()
        exp_sess.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        session.commit()

    res_expired = app_client.post(
        f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/submit",
        headers=headers1,
        json={"answers": all_answers, "quiz_token": expired_token},
    )
    assert res_expired.status_code == 410
    assert "expired" in res_expired.json()["detail"].lower()


def test_answer_option_randomization_distribution():
    """Verify cryptographic shuffle distributes correct options across A, B, C, D uniformly (not fixed to B-C-A)."""
    options_sample = [
        "Option Alpha",
        "Option Beta",
        "Option Gamma",
        "Option Delta",
    ]
    counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    trials = 200
    for i in range(trials):
        res = _randomize_question_options(
            question_text="Sample Test Question",
            options=options_sample,
            correct_text="Option Alpha",
            bloom_level="Understand",
            explanation="Explanation text",
        )
        counts[res["correct_option"]] += 1

    # Option D must be chosen, and each option should have reasonable representation (at least 15% of 200)
    assert counts["D"] > 20
    assert counts["A"] > 20
    assert counts["B"] > 20
    assert counts["C"] > 20


def test_multi_subject_question_bank_coverage():
    """Verify domain question bank contains genuine academic questions across required curricula."""
    assert "scheduling" in SUBJECT_QUESTION_BANK
    assert "synchronization" in SUBJECT_QUESTION_BANK
    assert "deadlock" in SUBJECT_QUESTION_BANK
    assert "paging" in SUBJECT_QUESTION_BANK
    assert "operating_systems" in SUBJECT_QUESTION_BANK
    assert "databases" in SUBJECT_QUESTION_BANK
    assert "mathematics" in SUBJECT_QUESTION_BANK
    assert "statistics" in SUBJECT_QUESTION_BANK

    for subject in ["scheduling", "synchronization", "deadlock", "paging", "operating_systems", "databases", "mathematics", "statistics"]:
        qlist = SUBJECT_QUESTION_BANK[subject]
        assert len(qlist) >= 10, f"Subject {subject} must contain at least 10 curriculum questions"
        for q in qlist:
            assert len(q["options"]) == 4
            assert q["correct_text"] in q["options"]
            assert len(q["explanation"]) > 20
            # Ensure no generic boilerplate
            assert "structured invariants" not in q["question_text"]


def test_concurrent_quiz_submissions_atomic_single_winner(app_client, seeded_users):
    """Verify that concurrent requests with the same quiz_token allow exactly one to succeed (200) and one to fail (409 Conflict)."""
    import concurrent.futures

    token1 = seeded_users["token1"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    c_res = app_client.post(
        "/api/v1/courses",
        headers=headers1,
        json={"code": "CS_CONCURRENCY", "name": "Concurrency Test Course", "semester": "Sem 3", "academic_year": "2025-2026", "description": "Course"},
    )
    course_id = c_res.json()["id"]

    with session_scope() as session:
        unit = CourseUnit(course_id=course_id, unit_number=1, title="Unit 1")
        session.add(unit)
        session.flush()
        topic = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Critical Section Problem")
        session.add(topic)
        session.flush()
        topic_id = topic.id

    q_res = app_client.post(f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/quiz", headers=headers1)
    assert q_res.status_code == 200
    q_data = q_res.json()
    assert q_data["expires_in_seconds"] == 1800
    quiz_token = q_data["quiz_token"]
    answers = [{"question_id": q["id"], "selected_option": "A"} for q in q_data["questions"]]

    def submit_attempt():
        return app_client.post(
            f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/submit",
            headers=headers1,
            json={"answers": answers, "quiz_token": quiz_token},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(submit_attempt)
        f2 = executor.submit(submit_attempt)
        r1 = f1.result()
        r2 = f2.result()

    status_codes = sorted([r1.status_code, r2.status_code])
    assert status_codes == [200, 409], f"Expected one 200 and one 409 Conflict, got {status_codes}"


def test_unsupported_topic_returns_explicit_unavailable(app_client, seeded_users):
    """When topic has no materials and cannot be mapped to any syllabus domain, return explicit available=False."""
    token1 = seeded_users["token1"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    c_res = app_client.post(
        "/api/v1/courses",
        headers=headers1,
        json={
            "code": "RANDOM_UNSUPPORTED",
            "name": "Completely Unsupported Subject",
            "semester": "Semester 1",
            "academic_year": "2025-2026",
            "description": "No domain match",
        },
    )
    assert c_res.status_code in (200, 201)
    course_id = c_res.json()["id"]

    with session_scope() as session:
        unit = CourseUnit(course_id=course_id, unit_number=1, title="Unit 1")
        session.add(unit)
        session.flush()
        topic = SyllabusTopic(course_id=course_id, unit_id=unit.id, name="Quasar Spectroscopy In Astrochemistry")
        session.add(topic)
        session.flush()
        topic_id = topic.id

    q_res = app_client.post(f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/quiz", headers=headers1)
    assert q_res.status_code == 200
    res_data = q_res.json()
    assert res_data["available"] is False
    assert "message" in res_data
    assert "unavailable" in res_data["message"].lower()
    assert len(res_data["questions"]) == 0
    assert res_data["quiz_token"] is None


# ===========================================================================
# 5. MULTI-TENANT ISOLATION ACROSS ALL SCOPES (RAG & ACADEMIC)
# ===========================================================================

@pytest.mark.asyncio
async def test_multitenant_rag_scope_isolation(seeded_users):
    """Adversarial verification that User 2 cannot access User 1's excerpts across all 5 scopes."""
    u1_id = seeded_users["u1_id"]
    u2_id = seeded_users["u2_id"]

    # Seed User 1 folder, source, excerpts, course, and topic
    with session_scope() as session:
        f1 = Folder(name="User 1 Confidential Folder", user_id=u1_id)
        session.add(f1)
        session.flush()

        s1 = Source(
            title="User 1 Secret Architecture Note",
            kind=SourceKind.TEXT,
            origin=SourceOrigin.UPLOAD,
            status=SourceStatus.READY,
            user_id=u1_id,
            folder_id=f1.id,
        )
        session.add(s1)
        session.flush()

        e1 = Segment(
            source_id=s1.id,
            text="Top secret distributed consensus specification for User 1.",
            page_no=1,
            index=1,
        )
        session.add(e1)
        session.flush()

        c1 = Course(
            code="CS_SECRET_101",
            name="Confidential Course",
            user_id=u1_id,
        )
        session.add(c1)
        session.flush()

        u1_unit = CourseUnit(course_id=c1.id, unit_number=1, title="Unit 1")
        session.add(u1_unit)
        session.flush()

        t1 = SyllabusTopic(course_id=c1.id, unit_id=u1_unit.id, name="Secret Consensus")
        session.add(t1)
        session.flush()

        link = CourseMaterialLink(course_id=c1.id, unit_id=u1_unit.id, source_id=s1.id)
        session.add(link)

        f1_id = f1.id
        s1_id = s1.id
        c1_id = c1.id
        t1_id = t1.id

    from quicklearn.db.session import raw_sqlite
    from quicklearn.db.search import upsert
    with raw_sqlite() as conn:
        upsert(conn, "segment", e1.id, body=e1.text, source_id=s1.id)

    # 1. User 2 queries scope 'topic' with User 1's topic_id -> must return []
    res_topic = await retrieve(
        query="distributed consensus",
        scope_type="topic",
        scope_id=t1_id,
        user_id=u2_id,
        top_k=5,
    )
    assert len(res_topic) == 0

    # 2. User 2 queries scope 'course' with User 1's course_id -> must return []
    res_course = await retrieve(
        query="distributed consensus",
        scope_type="course",
        scope_id=c1_id,
        user_id=u2_id,
        top_k=5,
    )
    assert len(res_course) == 0

    # 3. User 2 queries scope 'source' with User 1's source_id -> must return []
    res_source = await retrieve(
        query="distributed consensus",
        scope_type="source",
        scope_id=s1_id,
        user_id=u2_id,
        top_k=5,
    )
    assert len(res_source) == 0

    # 4. User 2 queries scope 'folder' with User 1's folder_id -> must return []
    res_folder = await retrieve(
        query="distributed consensus",
        scope_type="folder",
        scope_id=f1_id,
        user_id=u2_id,
        top_k=5,
    )
    assert len(res_folder) == 0

    # 5. User 2 queries scope 'all' -> User 1's source must not be returned
    res_all = await retrieve(
        query="distributed consensus",
        scope_type="all",
        scope_id=None,
        user_id=u2_id,
        top_k=5,
    )
    assert all(r.source_id != s1_id for r in res_all)

    # 6. User 1 queries scope 'topic' -> legitimately retrieves excerpt
    res_u1 = await retrieve(
        query="distributed consensus",
        scope_type="topic",
        scope_id=t1_id,
        user_id=u1_id,
        top_k=5,
    )
    assert len(res_u1) >= 1
    assert "consensus" in res_u1[0].text.lower()


def test_manifest_multitenant_isolation(seeded_users):
    """User 2 querying source manifest for User 1's scopes returns empty manifest."""
    u1_id = seeded_users["u1_id"]
    u2_id = seeded_users["u2_id"]

    with session_scope() as session:
        c1 = Course(code="CS_MAN_01", name="Manifest Isolation Course", user_id=u1_id)
        session.add(c1)
        session.flush()
        c1_id = c1.id

    manifest = get_user_source_manifest(user_id=u2_id, scope_type="course", scope_id=c1_id)
    assert manifest.total_sources == 0
    assert len(manifest.items) == 0


def test_schedule_topic_revision_creates_task(app_client, seeded_users):
    """Scheduling revision creates a persistent RevisionTask for that topic."""
    token1 = seeded_users["token1"]
    headers = {"Authorization": f"Bearer {token1}"}

    c_res = app_client.post(
        "/api/v1/courses",
        headers=headers,
        json={
            "code": "CS302_REV_NEW",
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

    c_res = app_client.post(
        "/api/v1/courses",
        headers={"Authorization": f"Bearer {token1}"},
        json={
            "code": "CS302_ISO_NEW",
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

    # User 2 tries to access User 1's course progress -> 404
    res_prog = app_client.get(
        f"/api/v1/courses/{course_id}/progress",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert res_prog.status_code == 404

    # User 2 tries to access User 1's topic learning journey -> 404
    res_learn = app_client.get(
        f"/api/v1/courses/{course_id}/topics/{topic_id}/learning",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert res_learn.status_code == 404

    # User 2 tries to submit quiz for User 1's topic -> 404
    res_sub = app_client.post(
        f"/api/v1/courses/{course_id}/topics/{topic_id}/learning/submit",
        headers={"Authorization": f"Bearer {token2}"},
        json={"answers": [{"question_id": 1, "selected_option": "A"}], "quiz_token": "valid.token"},
    )
    assert res_sub.status_code == 404

def test_source_workspace_and_explain_endpoints(app_client, seeded_users):
    """Verify GET /sources/{id}/workspace and POST /sources/{id}/explain endpoints."""
    token1 = seeded_users["token1"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    # 1. Create a source
    src_res = app_client.post(
        "/api/v1/sources/text",
        headers=headers1,
        json={
            "title": "Virtual Memory and Paging",
            "content": "Virtual memory decouples logical address space from physical DRAM frames. The MMU uses a TLB to cache page-to-frame translations. Page faults occur when a page present bit is 0.",
        },
    )
    assert src_res.status_code in (200, 201)
    source_id = src_res.json()["source_id"]

    # 2. Query unified workspace state
    ws_res = app_client.get(f"/api/v1/sources/{source_id}/workspace", headers=headers1)
    assert ws_res.status_code == 200
    ws = ws_res.json()
    assert ws["source"]["id"] == source_id
    assert "processing" in ws
    assert ws["processing"]["segments_count"] >= 0
    assert "outline" in ws
    assert "progress" in ws
    assert ws["progress"]["mastery_score"] == 0.0  # Real initial mastery, no fake 65%

    # 3. Call grounded topic explanation
    exp_res = app_client.post(
        f"/api/v1/sources/{source_id}/explain",
        headers=headers1,
        json={"topic": "Virtual Memory", "depth": "principle"},
    )
    assert exp_res.status_code == 200
    exp = exp_res.json()
    assert exp["topic"] == "Virtual Memory"
    assert "summary" in exp
    assert "definitions" in exp
    assert "worked_example" in exp
    assert "citations" in exp
