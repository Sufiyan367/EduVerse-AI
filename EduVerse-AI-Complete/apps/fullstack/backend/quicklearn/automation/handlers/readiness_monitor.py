"""Automation E: Exam Readiness Monitor.

Calculates realistic readiness heuristics from syllabus coverage, student mastery,
mock exam scores, and revision task completion. Flags untested topics and provides
timely risk indicators.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from sqlalchemy import func, select

from ...db.academic_models import (
    Course,
    ExamSession,
    Notification,
    RevisionPlan,
    RevisionTask,
    StudentTopicMastery,
    SyllabusTopic,
)
from ...db.enums import JobType
from ...db.session import session_scope
from ...db.types import utcnow
from ...jobs.worker import JobContext, register

log = logging.getLogger(__name__)


@register(JobType.AUTONOMOUS_READINESS)
async def handle_readiness_automation(ctx: JobContext) -> None:
    """Calculate exam readiness score and untested topic analysis for course."""
    course_id = ctx.payload.get("course_id")
    user_id = ctx.user_id or ctx.payload.get("user_id")

    if not course_id:
        raise ValueError("course_id is required for readiness monitor")

    ctx.progress(25, "Aggregating syllabus, mastery, exam, and revision metrics")

    with session_scope() as session:
        course = session.get(Course, course_id)
        if not course:
            raise ValueError(f"Course {course_id} not found")
        course_name = course.name

        topics = list(session.execute(select(SyllabusTopic).where(SyllabusTopic.course_id == course_id)).scalars())
        total_topics = len(topics)

        if total_topics == 0:
            ctx.progress(100, "No topics found in course")
            return

        topic_ids = [t.id for t in topics]

        # 1. Student Mastery
        mastery_records = list(
            session.execute(
                select(StudentTopicMastery).where(
                    StudentTopicMastery.user_id == user_id,
                    StudentTopicMastery.topic_id.in_(topic_ids),
                )
            ).scalars()
        )
        tested_topic_ids = {m.topic_id for m in mastery_records}
        untested_topics = [t.name for t in topics if t.id not in tested_topic_ids]

        coverage_pct = round((len(tested_topic_ids) / total_topics) * 100.0, 1)
        avg_mastery_pct = round(
            (sum(m.mastery_score for m in mastery_records) / max(1, len(mastery_records))) * 100.0, 1
        ) if mastery_records else 0.0

        # 2. Mock Exam Average
        exam_sessions = list(
            session.execute(
                select(ExamSession).where(
                    ExamSession.course_id == course_id,
                    ExamSession.user_id == user_id,
                    ExamSession.status == "completed",
                )
            ).scalars()
        )
        mock_avg_pct = 70.0
        if exam_sessions:
            mock_avg_pct = round(
                (sum((s.total_score or 0.0) for s in exam_sessions) / max(1, sum((s.max_score or 1.0) for s in exam_sessions))) * 100.0, 1
            )

        # 3. Revision Task Completion
        plans = list(
            session.execute(
                select(RevisionPlan).where(
                    RevisionPlan.course_id == course_id,
                    RevisionPlan.user_id == user_id,
                )
            ).scalars()
        )
        plan_ids = [p.id for p in plans]
        tasks = list(
            session.execute(
                select(RevisionTask).where(RevisionTask.plan_id.in_(plan_ids))
            ).scalars()
        ) if plan_ids else []

        completed_tasks = [t for t in tasks if t.is_completed]
        revision_completion_pct = round((len(completed_tasks) / max(1, len(tasks))) * 100.0, 1) if tasks else 50.0

        # 4. Readiness Heuristic Calculation
        # Coverage: 25%, Mastery: 35%, Mocks: 25%, Revision: 15%
        readiness_score = round(
            (coverage_pct * 0.25)
            + (avg_mastery_pct * 0.35)
            + (mock_avg_pct * 0.25)
            + (revision_completion_pct * 0.15),
            1,
        )

        level = "Ready" if readiness_score >= 80 else ("Needs Focus" if readiness_score >= 50 else "Critical")

        # In-app notification if below 60%
        if user_id and readiness_score < 60.0:
            notif = Notification(
                user_id=user_id,
                title=f"⚠️ Exam Readiness Alert: {course_name}",
                message=f"Current readiness is {readiness_score}% ({level}). {len(untested_topics)} untested syllabus topics require immediate practice.",
                kind="exam_readiness",
                link=f"/performance?course_id={course_id}",
                data={
                    "course_id": course_id,
                    "readiness_score": readiness_score,
                    "level": level,
                    "untested_count": len(untested_topics),
                },
            )
            session.add(notif)

    ctx.progress(100, f"Readiness score: {readiness_score}% ({level})")
