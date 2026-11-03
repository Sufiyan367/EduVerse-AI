"""Academic Domain Models for University Exam Intelligence & Adaptive Learning.

Entities:
- Course Workspace (Course, CourseUnit, CourseOutcome, SyllabusTopic, TopicOutcomeLink, CourseMaterialLink)
- Previous Paper Intelligence (PreviousPaper, ExamQuestion, QuestionTopicLink, ExamPattern, ExamBlueprint)
- Assessment Engine (Rubric, RubricCriterion, ExamSession, AssessmentQuestion, AnswerAttempt, GradingFeedback)
- Adaptive Learning (StudentTopicMastery, TopicMasteryEvent, RevisionPlan, RevisionTask, RemediationAttempt)

Strict multi-tenant isolation by user_id.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .types import UTCDateTime, utcnow


# ==========================================
# 1. COURSE WORKSPACE & SYLLABUS INTELLIGENCE
# ==========================================

class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255))
    semester: Mapped[str] = mapped_column(String(32), default="Semester 3")
    academic_year: Mapped[str] = mapped_column(String(32), default="2025-2026")
    description: Mapped[str] = mapped_column(Text, default="")
    target_exam_date: Mapped[dt.datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    units: Mapped[list[CourseUnit]] = relationship(back_populates="course", cascade="all, delete-orphan")
    outcomes: Mapped[list[CourseOutcome]] = relationship(back_populates="course", cascade="all, delete-orphan")
    topics: Mapped[list[SyllabusTopic]] = relationship(back_populates="course", cascade="all, delete-orphan")
    materials: Mapped[list[CourseMaterialLink]] = relationship(back_populates="course", cascade="all, delete-orphan")
    papers: Mapped[list[PreviousPaper]] = relationship(back_populates="course", cascade="all, delete-orphan")
    exam_sessions: Mapped[list[ExamSession]] = relationship(back_populates="course", cascade="all, delete-orphan")
    revision_plans: Mapped[list[RevisionPlan]] = relationship(back_populates="course", cascade="all, delete-orphan")


class CourseUnit(Base):
    __tablename__ = "course_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    unit_number: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    weightage_percent: Mapped[float] = mapped_column(Float, default=16.6)

    course: Mapped[Course] = relationship(back_populates="units")
    topics: Mapped[list[SyllabusTopic]] = relationship(back_populates="unit", cascade="all, delete-orphan")


class CourseOutcome(Base):
    __tablename__ = "course_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    co_code: Mapped[str] = mapped_column(String(32))  # CO1, CO2, etc.
    description: Mapped[str] = mapped_column(Text)
    target_level: Mapped[str] = mapped_column(String(32), default="Apply")  # Bloom's level

    course: Mapped[Course] = relationship(back_populates="outcomes")


class SyllabusTopic(Base):
    __tablename__ = "syllabus_topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("course_units.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    bloom_level: Mapped[str] = mapped_column(String(32), default="Understand")
    importance_score: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)

    course: Mapped[Course] = relationship(back_populates="topics")
    unit: Mapped[CourseUnit] = relationship(back_populates="topics")
    outcome_links: Mapped[list[TopicOutcomeLink]] = relationship(back_populates="topic", cascade="all, delete-orphan")
    question_links: Mapped[list[QuestionTopicLink]] = relationship(back_populates="topic", cascade="all, delete-orphan")
    mastery_records: Mapped[list[StudentTopicMastery]] = relationship(back_populates="topic", cascade="all, delete-orphan")


class TopicOutcomeLink(Base):
    __tablename__ = "topic_outcome_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("syllabus_topics.id", ondelete="CASCADE"), index=True)
    outcome_id: Mapped[int] = mapped_column(ForeignKey("course_outcomes.id", ondelete="CASCADE"), index=True)

    topic: Mapped[SyllabusTopic] = relationship(back_populates="outcome_links")
    outcome: Mapped[CourseOutcome] = relationship()


class CourseMaterialLink(Base):
    __tablename__ = "course_material_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("course_units.id", ondelete="SET NULL"), nullable=True)

    course: Mapped[Course] = relationship(back_populates="materials")


# ==========================================
# 2. PREVIOUS PAPER INTELLIGENCE & PATTERNS
# ==========================================

class PreviousPaper(Base):
    __tablename__ = "previous_papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    exam_term: Mapped[str] = mapped_column(String(64), default="End-Sem")
    exam_year: Mapped[int] = mapped_column(Integer, default=2024)
    total_marks: Mapped[float] = mapped_column(Float, default=70.0)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=150)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)

    course: Mapped[Course] = relationship(back_populates="papers")
    questions: Mapped[list[ExamQuestion]] = relationship(back_populates="paper", cascade="all, delete-orphan")


class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("previous_papers.id", ondelete="CASCADE"), index=True)
    question_number: Mapped[str] = mapped_column(String(32), default="Q1")
    question_text: Mapped[str] = mapped_column(Text)
    marks: Mapped[float] = mapped_column(Float, default=5.0)
    bloom_level: Mapped[str] = mapped_column(String(32), default="Understand")
    frequency_count: Mapped[int] = mapped_column(Integer, default=1)

    paper: Mapped[PreviousPaper] = relationship(back_populates="questions")
    topic_links: Mapped[list[QuestionTopicLink]] = relationship(back_populates="question", cascade="all, delete-orphan")


class QuestionTopicLink(Base):
    __tablename__ = "question_topic_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("exam_questions.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("syllabus_topics.id", ondelete="CASCADE"), index=True)
    relevance_score: Mapped[float] = mapped_column(Float, default=1.0)

    question: Mapped[ExamQuestion] = relationship(back_populates="topic_links")
    topic: Mapped[SyllabusTopic] = relationship(back_populates="question_links")


class ExamPattern(Base):
    __tablename__ = "exam_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    pattern_type: Mapped[str] = mapped_column(String(64))  # e.g. "SPPU 70-Marks Pattern"
    structure: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ExamBlueprint(Base):
    __tablename__ = "exam_blueprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    unit_distribution: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    bloom_distribution: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


# ==========================================
# 3. RUBRIC-BASED ASSESSMENT & EXAM SIMULATOR
# ==========================================

class Rubric(Base):
    __tablename__ = "rubrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)

    criteria: Mapped[list[RubricCriterion]] = relationship(back_populates="rubric", cascade="all, delete-orphan")


class RubricCriterion(Base):
    __tablename__ = "rubric_criteria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rubric_id: Mapped[int] = mapped_column(ForeignKey("rubrics.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    max_points: Mapped[float] = mapped_column(Float, default=5.0)
    description: Mapped[str] = mapped_column(Text, default="")

    rubric: Mapped[Rubric] = relationship(back_populates="criteria")


class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="in_progress")  # in_progress, submitted, graded
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[float] = mapped_column(Float, default=50.0)
    started_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)
    submitted_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime, nullable=True)

    course: Mapped[Course] = relationship(back_populates="exam_sessions")
    questions: Mapped[list[AssessmentQuestion]] = relationship(back_populates="session", cascade="all, delete-orphan")
    attempts: Mapped[list[AnswerAttempt]] = relationship(back_populates="session", cascade="all, delete-orphan")


class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("exam_sessions.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("syllabus_topics.id", ondelete="SET NULL"), nullable=True)
    question_text: Mapped[str] = mapped_column(Text)
    ideal_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    marks: Mapped[float] = mapped_column(Float, default=10.0)
    question_order: Mapped[int] = mapped_column(Integer, default=1)

    session: Mapped[ExamSession] = relationship(back_populates="questions")
    attempts: Mapped[list[AnswerAttempt]] = relationship(back_populates="question", cascade="all, delete-orphan")


class AnswerAttempt(Base):
    __tablename__ = "answer_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("exam_sessions.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("assessment_questions.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    student_answer: Mapped[str] = mapped_column(Text)
    submitted_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)

    session: Mapped[ExamSession] = relationship(back_populates="attempts")
    question: Mapped[AssessmentQuestion] = relationship(back_populates="attempts")
    feedback: Mapped[GradingFeedback | None] = relationship(back_populates="attempt", uselist=False, cascade="all, delete-orphan")


class GradingFeedback(Base):
    __tablename__ = "grading_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("answer_attempts.id", ondelete="CASCADE"), unique=True, index=True)
    score_awarded: Mapped[float] = mapped_column(Float, default=0.0)
    evaluator_model: Mapped[str] = mapped_column(String(64), default="qwen3.5:4b")
    criterion_scores: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    strengths: Mapped[str] = mapped_column(Text, default="")
    weaknesses: Mapped[str] = mapped_column(Text, default="")
    suggestions: Mapped[str] = mapped_column(Text, default="")
    graded_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)

    attempt: Mapped[AnswerAttempt] = relationship(back_populates="feedback")


# ==========================================
# 4. ADAPTIVE LEARNING & MASTERY GRAPH
# ==========================================

class StudentTopicMastery(Base):
    __tablename__ = "student_topic_mastery"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("syllabus_topics.id", ondelete="CASCADE"), index=True)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 to 1.0
    confidence_level: Mapped[str] = mapped_column(String(32), default="low")  # low, medium, high
    status: Mapped[str] = mapped_column(String(32), default="not_started")  # not_started, learning, practicing, needs_review, mastered
    last_evaluated_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime, nullable=True, default=None)

    __table_args__ = (UniqueConstraint("user_id", "topic_id", name="uq_user_topic_mastery"),)

    topic: Mapped[SyllabusTopic] = relationship(back_populates="mastery_records")


class TopicMasteryEvent(Base):
    __tablename__ = "topic_mastery_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("syllabus_topics.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(32), default="quiz")  # quiz, exam, flashcard, remediation
    score: Mapped[float] = mapped_column(Float, default=0.0)
    recorded_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)


class RevisionPlan(Base):
    __tablename__ = "revision_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    target_date: Mapped[dt.datetime | None] = mapped_column(UTCDateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")  # active, completed
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)

    course: Mapped[Course] = relationship(back_populates="revision_plans")
    tasks: Mapped[list[RevisionTask]] = relationship(back_populates="plan", cascade="all, delete-orphan")


class RevisionTask(Base):
    __tablename__ = "revision_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("revision_plans.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("syllabus_topics.id", ondelete="SET NULL"), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=1)  # 1: High, 2: Medium, 3: Low
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=30)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime, nullable=True)

    plan: Mapped[RevisionPlan] = relationship(back_populates="tasks")
    remediations: Mapped[list[RemediationAttempt]] = relationship(back_populates="task", cascade="all, delete-orphan")


class RemediationAttempt(Base):
    __tablename__ = "remediation_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("revision_tasks.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    action_type: Mapped[str] = mapped_column(String(64), default="practice_quiz")
    performance_delta: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)

    task: Mapped[RevisionTask] = relationship(back_populates="remediations")


# ==========================================
# 5. AUTONOMOUS AUTOMATION & AUDIT ENGINE
# ==========================================

class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    rule_name: Mapped[str] = mapped_column(String(64), index=True)
    trigger_event: Mapped[str] = mapped_column(String(64), index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=True, index=True)
    week_start: Mapped[dt.datetime] = mapped_column(UTCDateTime)
    week_end: Mapped[dt.datetime] = mapped_column(UTCDateTime)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    strong_topics: Mapped[list[Any]] = mapped_column(JSON, default=list)
    weak_topics: Mapped[list[Any]] = mapped_column(JSON, default=list)
    repeated_mistakes: Mapped[list[Any]] = mapped_column(JSON, default=list)
    revision_completion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    summary_text: Mapped[str] = mapped_column(Text, default="")
    recommendations: Mapped[list[Any]] = mapped_column(JSON, default=list)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(64), default="info")  # revision_alert, automation_completed, audit_warning, exam_readiness
    link: Mapped[str | None] = mapped_column(String(255), nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)


class EvidenceAuditIssue(Base):
    __tablename__ = "evidence_audit_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=True, index=True)
    issue_type: Mapped[str] = mapped_column(String(64), index=True)  # ambiguous_mapping, missing_citation, invalid_rubric_weight, out_of_bounds, orphaned_mastery
    severity: Mapped[str] = mapped_column(String(32), default="warning")  # warning, error, review_required
    entity_type: Mapped[str] = mapped_column(String(64))  # source, topic_mapping, question, rubric, mastery
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text)
    evidence_context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)  # open, resolved, dismissed
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)
    resolved_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime, nullable=True)
