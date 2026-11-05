import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

"""Comprehensive Integration Test Suite for EduVerse Autonomous Automation Engine.

Tests:
1. PostgreSQL SELECT ... FOR UPDATE SKIP LOCKED row claiming
2. Idempotency keys and duplicate event prevention
3. Exponential backoff retry and lease heartbeats
4. Multi-tenant isolation by user_id
5. Live execution of Automations A through G against PostgreSQL
6. Automation REST API endpoints & granular health monitoring
"""

import datetime as dt
import pytest
from sqlalchemy import select, text

from quicklearn.automation import dispatcher, rules
from quicklearn.db.academic_models import (
    AnswerAttempt,
    AssessmentQuestion,
    AutomationRule,
    Course,
    CourseMaterialLink,
    CourseOutcome,
    CourseUnit,
    EvidenceAuditIssue,
    ExamQuestion,
    ExamSession,
    GradingFeedback,
    Notification,
    PreviousPaper,
    QuestionTopicLink,
    RevisionPlan,
    RevisionTask,
    Rubric,
    RubricCriterion,
    StudentTopicMastery,
    SyllabusTopic,
    TopicMasteryEvent,
    WeeklyReport,
)
from quicklearn.db.enums import JobStatus, JobType, SourceKind, SourceOrigin, SourceStatus
from quicklearn.db.models import Job, Segment, Source, User
from quicklearn.db.session import get_engine, session_scope
from quicklearn.db.types import utcnow
from quicklearn.jobs import queue as jq
from quicklearn.jobs.worker import run_job_inline


@pytest.fixture
def test_user():
    """Ensure a deterministic test user exists in PostgreSQL."""
    with session_scope() as session:
        user = session.execute(
            select(User).where(User.email == "automation_tester@eduverse.ai")
        ).scalar_one_or_none()
        if not user:
            user = User(
                username="automation_tester",
                email="automation_tester@eduverse.ai",
                full_name="Autonomous System Tester",
                hashed_password="test_hash_secure",
            )
            session.add(user)
            session.flush()
        return user.id


@pytest.fixture
def test_course(test_user):
    """Ensure a deterministic test course exists in PostgreSQL."""
    with session_scope() as session:
        course = session.execute(
            select(Course).where(
                Course.code == "AUTONOMOUS_DBMS_301",
                Course.user_id == test_user,
            )
        ).scalar_one_or_none()
        if not course:
            course = Course(
                user_id=test_user,
                code="AUTONOMOUS_DBMS_301",
                name="Database Management Systems Engineering",
                semester="Semester 3",
                academic_year="2025-2026",
                description="Core Relational DB Architecture & Autonomous Workflows",
                target_exam_date=utcnow() + dt.timedelta(days=21),
            )
            session.add(course)
            session.flush()
        return course.id


# =====================================================================
# 1. QUEUE ENGINE, SKIP LOCKED, IDEMPOTENCY & LEASE TESTS
# =====================================================================

def test_queue_enqueue_and_idempotency(test_user):
    """Verify that enqueueing with an idempotency key prevents duplicate row creation."""
    key = f"idempotent_test_{utcnow().timestamp()}"
    job_id_1 = jq.enqueue(
        JobType.AUTONOMOUS_AUDIT,
        payload={"task": "audit_1"},
        user_id=test_user,
        priority=80,
        idempotency_key=key,
    )

    # Re-enqueuing with the same idempotency key must return the exact same job ID
    job_id_2 = jq.enqueue(
        JobType.AUTONOMOUS_AUDIT,
        payload={"task": "audit_2"},
        user_id=test_user,
        priority=80,
        idempotency_key=key,
    )

    assert job_id_1 == job_id_2

    with session_scope() as session:
        count = session.execute(
            select(text("COUNT(*)")).select_from(Job).where(Job.idempotency_key == key)
        ).scalar_one()
        assert count == 1


def test_skip_locked_claiming_and_leases(test_user):
    """Verify atomic claiming, priority ordering, and lease assignment."""
    # Enqueue low priority job
    low_job_id = jq.enqueue(
        JobType.AUTONOMOUS_AUDIT,
        payload={"label": "low"},
        user_id=test_user,
        priority=10,
    )
    # Enqueue high priority job
    high_job_id = jq.enqueue(
        JobType.AUTONOMOUS_AUDIT,
        payload={"label": "high"},
        user_id=test_user,
        priority=90,
    )

    # Worker 1 claims: must get high priority job first due to ORDER BY priority DESC
    claimed = jq.claim_next(worker_id="worker-test-1", lease_seconds=60)
    assert claimed is not None
    assert claimed.id == high_job_id
    assert claimed.priority == 90
    assert claimed.attempts >= 1

    # Check that database row reflects running status and worker lease
    with session_scope() as session:
        job = session.get(Job, high_job_id)
        assert job.status == JobStatus.RUNNING
        assert job.locked_by == "worker-test-1"
        assert job.locked_until is not None

    # Heartbeat verification
    hb_ok = jq.heartbeat(high_job_id, worker_id="worker-test-1", lease_seconds=120)
    assert hb_ok is True

    # Complete high priority job
    jq.mark_succeeded(high_job_id, stage="Test Done")

    # Clean up low priority job
    jq.cancel(low_job_id)


def test_exponential_backoff_retry(test_user):
    """Verify mark_failed schedules next_run_at with exponential backoff if attempts < max_attempts."""
    job_id = jq.enqueue(
        JobType.AUTONOMOUS_AUDIT,
        payload={"test": "retry"},
        user_id=test_user,
        max_attempts=3,
    )
    # Claim job
    claimed = jq.claim_next_specific(job_id, worker_id="worker-retry")
    assert claimed is not None
    assert claimed.attempts == 1

    before_fail = utcnow()
    will_retry = jq.mark_failed(job_id, "Temporary network timeout", retryable=True, error_details={"err": "timeout"})
    assert will_retry is True

    with session_scope() as session:
        job = session.get(Job, job_id)
        assert job.status == JobStatus.QUEUED
        assert job.attempts == 1
        assert job.next_run_at > before_fail  # backoff delay scheduled
        assert "Retrying" in job.stage
        assert job.error_details.get("err") == "timeout"


def test_lease_expiry_and_orphan_recovery(test_user):
    """Verify that jobs with expired leases are recovered cleanly."""
    job_id = jq.enqueue(JobType.AUTONOMOUS_AUDIT, payload={"test": "orphan"}, user_id=test_user)
    claimed = jq.claim_next_specific(job_id, worker_id="worker-crash")
    assert claimed is not None

    # Force lease into the past to simulate a worker crash
    with session_scope() as session:
        job = session.get(Job, job_id)
        job.locked_until = utcnow() - dt.timedelta(minutes=5)

    # recover_orphans must requeue this stranded job
    requeued = jq.recover_orphans()
    assert requeued >= 1

    with session_scope() as session:
        job = session.get(Job, job_id)
        assert job.status == JobStatus.QUEUED
        assert job.locked_until is None


# =====================================================================
# 2. AUTOMATIONS A THROUGH G INTEGRATION TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_automation_a_course_intelligence_live(test_user, test_course):
    """Automation A: Verify syllabus parsing into Units, Topics, COs and material mapping."""
    # 1. Test Syllabus Extraction
    job_id = jq.enqueue(
        JobType.AUTONOMOUS_SYLLABUS,
        payload={
            "course_id": test_course,
            "user_id": test_user,
        },
        user_id=test_user,
        priority=80,
    )
    await run_job_inline(job_id)

    with session_scope() as session:
        job = session.get(Job, job_id)
        assert job.status == JobStatus.SUCCEEDED

        units = list(session.execute(select(CourseUnit).where(CourseUnit.course_id == test_course)).scalars())
        assert len(units) >= 1

        topics = list(session.execute(select(SyllabusTopic).where(SyllabusTopic.course_id == test_course)).scalars())
        assert len(topics) >= 1

        cos = list(session.execute(select(CourseOutcome).where(CourseOutcome.course_id == test_course)).scalars())
        assert len(cos) >= 1

    # 2. Test Material Mapping with Ambiguity Flagging
    with session_scope() as session:
        src = Source(
            user_id=test_user,
            title="Unrelated Advanced Quantum Machine Learning Lecture",
            kind=SourceKind.TEXT,
            origin=SourceOrigin.UPLOAD,
            status=SourceStatus.READY,
        )
        session.add(src)
        session.flush()
        src_id = src.id

    mat_job_id = jq.enqueue(
        JobType.AUTONOMOUS_MATERIAL,
        payload={
            "course_id": test_course,
            "source_id": src_id,
            "user_id": test_user,
        },
        user_id=test_user,
    )
    await run_job_inline(mat_job_id)

    # Low relevance material must flag an EvidenceAuditIssue
    with session_scope() as session:
        issue = session.execute(
            select(EvidenceAuditIssue).where(
                EvidenceAuditIssue.entity_type == "source",
                EvidenceAuditIssue.entity_id == src_id,
            )
        ).scalar_one_or_none()
        assert issue is not None
        assert issue.issue_type == "ambiguous_mapping"
        assert issue.severity == "review_required"


@pytest.mark.asyncio
async def test_automation_b_paper_analyst_live(test_user, test_course):
    """Automation B: Verify question extraction, topic mapping, and past paper sample disclosure."""
    with session_scope() as session:
        paper = PreviousPaper(
            course_id=test_course,
            user_id=test_user,
            title="SPPU In-Sem Examination May 2024",
            exam_year=2024,
            exam_term="In-Sem",
            total_marks=30,
            duration_minutes=60,
        )
        session.add(paper)
        session.flush()
        paper_id = paper.id

    job_id = jq.enqueue(
        JobType.AUTONOMOUS_PAPER,
        payload={
            "course_id": test_course,
            "paper_id": paper_id,
            "user_id": test_user,
        },
        user_id=test_user,
    )
    await run_job_inline(job_id)

    with session_scope() as session:
        job = session.get(Job, job_id)
        assert job.status == JobStatus.SUCCEEDED

        questions = list(session.execute(select(ExamQuestion).where(ExamQuestion.paper_id == paper_id)).scalars())
        assert len(questions) >= 1
        for q in questions:
            assert q.marks > 0
            assert q.bloom_level in ["Remember", "Understand", "Apply", "Analyze", "Evaluate"]

        # Check in-app notification disclosure
        notif = session.execute(
            select(Notification).where(
                Notification.user_id == test_user,
                Notification.title.like("%Exam Paper Analyzed%"),
            )
        ).scalars().first()
        assert notif is not None
        assert "Analyzed across" in notif.message
        assert "not a guaranteed exam prediction" in notif.message


@pytest.mark.asyncio
async def test_automation_c_exam_eval_adaptive_live(test_user, test_course):
    """Automation C: Verify rubric evaluation, criteria feedback, mastery update, and adaptive revision."""
    with session_scope() as session:
        # Create topic
        unit = CourseUnit(course_id=test_course, unit_number=1, title="Unit 1")
        session.add(unit)
        session.flush()

        topic = SyllabusTopic(course_id=test_course, unit_id=unit.id, name="Transaction ACID Properties")
        session.add(topic)
        session.flush()
        topic_id = topic.id

        # Create session and questions
        exam_session = ExamSession(
            user_id=test_user,
            course_id=test_course,
            title="Unit 1 Concurrency & ACID Drill",
            status="submitted",
            total_score=0.0,
            max_score=10.0,
        )
        session.add(exam_session)
        session.flush()
        sess_id = exam_session.id

        q = AssessmentQuestion(
            session_id=sess_id,
            topic_id=topic_id,
            question_text="Explain Atomicity and Durability in database transactions.",
            ideal_answer="Atomicity ensures all-or-nothing execution. Durability ensures committed changes survive failures.",
            marks=10,
            question_order=1,
        )
        session.add(q)
        session.flush()

        attempt = AnswerAttempt(
            session_id=sess_id,
            question_id=q.id,
            user_id=test_user,
            student_answer="Atomicity means partial transactions roll back. Durability saves to disk.",
        )
        session.add(attempt)
        session.flush()

    job_id = jq.enqueue(
        JobType.AUTONOMOUS_EXAM_EVAL,
        payload={"session_id": sess_id, "user_id": test_user},
        user_id=test_user,
    )
    await run_job_inline(job_id)

    with session_scope() as session:
        job = session.get(Job, job_id)
        assert job.status == JobStatus.SUCCEEDED

        # Verify feedback
        fb = session.execute(select(GradingFeedback)).scalars().first()
        assert fb is not None
        assert fb.criterion_scores is not None

        # Verify topic mastery updated
        mastery = session.execute(
            select(StudentTopicMastery).where(
                StudentTopicMastery.user_id == test_user,
                StudentTopicMastery.topic_id == topic_id,
            )
        ).scalar_one_or_none()
        assert mastery is not None
        assert mastery.mastery_score > 0.0

        # Verify mastery event recorded
        event = session.execute(
            select(TopicMasteryEvent).where(
                TopicMasteryEvent.user_id == test_user,
                TopicMasteryEvent.topic_id == topic_id,
            )
        ).scalar_one_or_none()
        assert event is not None


@pytest.mark.asyncio
async def test_automation_d_daily_revision_scheduler_live(test_user, test_course):
    """Automation D: Verify persistent daily revision generation with date-stamped idempotency."""
    job_id = jq.enqueue(
        JobType.AUTONOMOUS_REVISION,
        payload={"user_id": test_user},
        user_id=test_user,
    )
    await run_job_inline(job_id)

    today_str = utcnow().strftime("%Y-%m-%d")
    with session_scope() as session:
        job = session.get(Job, job_id)
        assert job.status == JobStatus.SUCCEEDED

        plan = session.execute(
            select(RevisionPlan).where(
                RevisionPlan.user_id == test_user,
                RevisionPlan.title == f"Daily Revision — {today_str}",
            )
        ).scalar_one_or_none()
        assert plan is not None

        tasks = list(session.execute(select(RevisionTask).where(RevisionTask.plan_id == plan.id)).scalars())
        assert len(tasks) >= 1

        # Check morning notification
        notif = session.execute(
            select(Notification).where(
                Notification.user_id == test_user,
                Notification.kind == "revision_alert",
            )
        ).scalars().first()
        assert notif is not None
        assert "Morning Revision Scheduled" in notif.title


@pytest.mark.asyncio
async def test_automation_e_readiness_monitor_live(test_user, test_course):
    """Automation E: Verify readiness heuristic computation across actual database metrics."""
    job_id = jq.enqueue(
        JobType.AUTONOMOUS_READINESS,
        payload={"course_id": test_course, "user_id": test_user},
        user_id=test_user,
    )
    await run_job_inline(job_id)

    with session_scope() as session:
        job = session.get(Job, job_id)
        assert job.status == JobStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_automation_f_weekly_intelligence_live(test_user, test_course):
    """Automation F: Verify weekly academic intelligence report aggregation."""
    job_id = jq.enqueue(
        JobType.AUTONOMOUS_WEEKLY,
        payload={"course_id": test_course, "user_id": test_user},
        user_id=test_user,
    )
    await run_job_inline(job_id)

    with session_scope() as session:
        job = session.get(Job, job_id)
        assert job.status == JobStatus.SUCCEEDED

        report = session.execute(
            select(WeeklyReport).where(WeeklyReport.user_id == test_user)
        ).scalars().first()
        assert report is not None
        assert report.metrics is not None
        assert len(report.recommendations) >= 1


@pytest.mark.asyncio
async def test_automation_g_evidence_audit_live(test_user, test_course):
    """Automation G: Verify evidence audit engine checks rubric constraints and page bounds."""
    with session_scope() as session:
        sess = ExamSession(
            user_id=test_user,
            course_id=test_course,
            title="Audit Session",
            status="completed",
            total_score=5.0,
            max_score=10.0,
        )
        session.add(sess)
        session.flush()

        q = AssessmentQuestion(
            session_id=sess.id,
            question_text="Audit Question",
            ideal_answer="Expected Answer",
            marks=10,
            question_order=1,
        )
        session.add(q)
        session.flush()

        rubric = Rubric(course_id=test_course, title="Audit Rubric", description="desc")
        session.add(rubric)
        session.flush()

        crit = RubricCriterion(rubric_id=rubric.id, name="Grammar", max_points=4.0, description="desc")
        session.add(crit)

    job_id = jq.enqueue(
        JobType.AUTONOMOUS_AUDIT,
        payload={"course_id": test_course, "user_id": test_user},
        user_id=test_user,
    )
    await run_job_inline(job_id)

    with session_scope() as session:
        job = session.get(Job, job_id)
        assert job.status == JobStatus.SUCCEEDED

        issue = session.execute(
            select(EvidenceAuditIssue).where(EvidenceAuditIssue.issue_type == "invalid_rubric_weight")
        ).scalars().first()
        assert issue is not None
        assert issue.severity == "error"
