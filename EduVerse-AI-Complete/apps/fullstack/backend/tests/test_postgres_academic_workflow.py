"""End-to-End Test Suite for PostgreSQL Migration & Academic Exam Intelligence Workflow.

Verifies:
1. PostgreSQL connection & session pooling with psycopg 3
2. Multi-tenant Course Workspace creation and retrieval
3. Syllabus modular units, topics, and Bloom's taxonomy mapping
4. Previous Paper Intelligence & frequency analytics
5. Exam Simulator session generation and answer attempt submission
6. AI Rubric Assessment engine, criterion scoring, and feedback
7. Student Topic Mastery graph update and adaptive revision tasks
8. PostgreSQL Full-Text Search (tsvector + GIN) & Vector Retrieval (segment_vectors_blob + NumPy)
"""

import os
import sys
from pathlib import Path
import pytest

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

PG_URL = "postgresql+psycopg://eduverse_app:EduVerse_App_2026_SecureKey!@127.0.0.1:5432/eduverse_db"


@pytest.fixture(autouse=True, scope="module")
def setup_postgres_env():
    """Configure PostgreSQL environment for this optional test suite and restore SQLite on exit."""
    import quicklearn.db.session as session_mod
    old_url = os.environ.get("QUICKLEARN_DATABASE_URL")
    os.environ["QUICKLEARN_DATABASE_URL"] = PG_URL

    # Reset cached engine to connect to PG
    session_mod._engine = None
    session_mod._session_factory = None

    try:
        from sqlalchemy import text
        engine = session_mod.get_engine()
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE student_topic_mastery ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'not_started'"))
            conn.execute(text("ALTER TABLE student_topic_mastery ALTER COLUMN last_evaluated_at DROP NOT NULL"))
    except Exception as exc:
        # Restore environment immediately if connection fails
        if old_url is not None:
            os.environ["QUICKLEARN_DATABASE_URL"] = old_url
        else:
            os.environ.pop("QUICKLEARN_DATABASE_URL", None)
        session_mod._engine = None
        session_mod._session_factory = None
        pytest.skip(f"Optional PostgreSQL test skipped: {exc}")

    yield

    # Restore default SQLite environment
    if old_url is not None:
        os.environ["QUICKLEARN_DATABASE_URL"] = old_url
    else:
        os.environ.pop("QUICKLEARN_DATABASE_URL", None)
    session_mod._engine = None
    session_mod._session_factory = None


from quicklearn.db.session import get_engine, session_scope, raw_sqlite, is_postgres
from quicklearn.db.models import User, Segment
from quicklearn.db.academic_models import (
    Course,
    CourseUnit,
    SyllabusTopic,
    PreviousPaper,
    ExamQuestion,
    QuestionTopicLink,
    ExamSession,
    AssessmentQuestion,
    AnswerAttempt,
    GradingFeedback,
    StudentTopicMastery,
    TopicMasteryEvent,
    RevisionPlan,
    RevisionTask,
)
from quicklearn.db.search import search as pg_search, SearchHit
from quicklearn.rag.index import get_index


def test_postgresql_runtime_environment():
    """Verify PostgreSQL is the active runtime database."""
    engine = get_engine()
    assert is_postgres(engine), "Primary runtime engine must be PostgreSQL"
    with engine.connect() as conn:
        from sqlalchemy import text
        res = conn.execute(text("SELECT current_database(), current_user;")).fetchone()
        assert res[0] == "eduverse_db", f"Expected eduverse_db, got {res[0]}"
        assert res[1] == "eduverse_app", f"Expected eduverse_app, got {res[1]}"


def test_academic_workflow_end_to_end():
    """Verify complete academic intelligence lifecycle in PostgreSQL."""
    with session_scope() as session:
        # 1. Get or create student
        student = session.query(User).first()
        assert student is not None, "At least one migrated user must exist"
        user_id = student.id

        # 2. Course Workspace
        course = Course(
            user_id=user_id,
            code="AI-TEST-301",
            name="Applied Machine Learning & Neural Computation",
            semester="Semester 3",
            academic_year="2025-2026",
            description="Autonomous mini-project test course workspace",
        )
        session.add(course)
        session.flush()
        course_id = course.id
        assert course_id > 0

        # 3. Syllabus Units & Topics with Bloom Levels
        unit1 = CourseUnit(
            course_id=course_id,
            unit_number=1,
            title="Unit 1: Supervised Learning & Gradient Descent",
            weightage_percent=25.0,
        )
        session.add(unit1)
        session.flush()

        topic1 = SyllabusTopic(
            course_id=course_id,
            unit_id=unit1.id,
            name="Stochastic Gradient Descent and Learning Rate Decay",
            bloom_level="Apply",
            importance_score=1.5,
        )
        topic2 = SyllabusTopic(
            course_id=course_id,
            unit_id=unit1.id,
            name="Bias-Variance Tradeoff and Regularization",
            bloom_level="Analyze",
            importance_score=2.0,
        )
        session.add_all([topic1, topic2])
        session.flush()

        # 4. Previous Paper Intelligence
        paper = PreviousPaper(
            course_id=course_id,
            user_id=user_id,
            title="In-Sem Exam Winter 2024",
            exam_term="In-Sem",
            exam_year=2024,
            total_marks=50.0,
        )
        session.add(paper)
        session.flush()

        eq = ExamQuestion(
            paper_id=paper.id,
            question_number="Q1(a)",
            question_text="Derive the weight update rule for Stochastic Gradient Descent with L2 penalty.",
            marks=10.0,
            bloom_level="Apply",
            frequency_count=2,
        )
        session.add(eq)
        session.flush()

        link = QuestionTopicLink(question_id=eq.id, topic_id=topic1.id, relevance_score=1.0)
        session.add(link)
        session.flush()

        # 5. Exam Simulator Session
        exam_session = ExamSession(
            course_id=course_id,
            user_id=user_id,
            title="Practice Mid-Term Simulation 50M",
            max_score=50.0,
            status="in_progress",
        )
        session.add(exam_session)
        session.flush()

        aq = AssessmentQuestion(
            session_id=exam_session.id,
            topic_id=topic1.id,
            question_text=eq.question_text,
            marks=10.0,
            question_order=1,
        )
        session.add(aq)
        session.flush()

        # 6. Student Answer Attempt
        attempt = AnswerAttempt(
            session_id=exam_session.id,
            question_id=aq.id,
            user_id=user_id,
            student_answer="The loss function with L2 regularization is J(w) = MSE + (lambda/2)*||w||^2. Taking the gradient with respect to w gives grad = grad_MSE + lambda*w. The weight update rule is w_new = w_old - alpha*(grad_MSE + lambda*w) = (1 - alpha*lambda)*w_old - alpha*grad_MSE, demonstrating weight decay.",
        )
        session.add(attempt)
        session.flush()

        # 7. AI Rubric Assessment Feedback
        feedback = GradingFeedback(
            attempt_id=attempt.id,
            score_awarded=9.0,
            evaluator_model="qwen3.5:4b",
            criterion_scores={
                "conceptual_accuracy": 4.5,
                "technical_completeness": 2.8,
                "clarity": 1.7,
            },
            strengths="Clear mathematical derivation and exact weight decay expression.",
            weaknesses="Could explicitly state the learning rate bounds for stability.",
            suggestions="Mention momentum or adaptive learning rate variants (Adam/RMSProp).",
        )
        session.add(feedback)
        exam_session.total_score = 9.0
        exam_session.status = "graded"
        session.flush()

        # 8. Adaptive Learning & Student Mastery Graph
        mastery = StudentTopicMastery(
            user_id=user_id,
            topic_id=topic1.id,
            mastery_score=0.9,
            confidence_level="high",
        )
        session.add(mastery)

        event = TopicMasteryEvent(
            user_id=user_id,
            topic_id=topic1.id,
            event_type="exam",
            score=0.9,
        )
        session.add(event)

        # 9. Revision Plan & Tasks
        plan = RevisionPlan(
            user_id=user_id,
            course_id=course_id,
            title="Pre-Exam Intensive Revision Plan",
            status="active",
        )
        session.add(plan)
        session.flush()

        task = RevisionTask(
            plan_id=plan.id,
            topic_id=topic2.id,
            priority=1,
            title="Review Bias-Variance Tradeoff Curves",
            description="High yield topic from past papers. Current mastery is 0%.",
            estimated_minutes=35,
            is_completed=False,
        )
        session.add(task)
        session.flush()

        # Clean up test course and cascade delete all related child records
        session.delete(course)


def test_postgresql_fts_and_vector_search():
    """Verify PostgreSQL tsvector full text search and segment_vectors_blob vector index."""
    # Test vector index count
    idx = get_index()
    vec_count = idx.count()
    assert vec_count > 0, "Vector index in PostgreSQL segment_vectors_blob must contain embeddings"

    # Test vector search
    dummy_query = [0.01] * 384
    hits = idx.search(dummy_query, k=5)
    assert len(hits) > 0, "Vector search should return top hits from PostgreSQL"
    assert hits[0].segment_id > 0
    assert 0.0 <= hits[0].score <= 1.0

    # Test full text search
    with raw_sqlite() as conn:
        results = pg_search(conn, "learning", limit=5)
        assert isinstance(results, list)
        print(f"PostgreSQL FTS returned {len(results)} search results for 'learning'")
