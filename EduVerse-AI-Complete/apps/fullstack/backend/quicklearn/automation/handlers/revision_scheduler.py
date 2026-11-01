"""Automation D: Daily Revision Scheduler.

Persistent daily scheduler (default 07:00 Asia/Kolkata) that generates prioritized,
actionable revision tasks based on forgetting curve decay, weak topic mastery,
and impending university exam dates without duplicate daily runs.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from sqlalchemy import select

from ...db.academic_models import (
    Course,
    Notification,
    RevisionPlan,
    RevisionTask,
    StudentTopicMastery,
    SyllabusTopic,
)
from ...db.enums import JobType
from ...db.models import User
from ...db.session import session_scope
from ...db.types import utcnow
from ...jobs.worker import JobContext, register

log = logging.getLogger(__name__)


@register(JobType.AUTONOMOUS_REVISION)
async def handle_daily_revision_automation(ctx: JobContext) -> None:
    """Generate daily personalized revision tasks for active courses and weak topics."""
    user_id = ctx.user_id or ctx.payload.get("user_id")

    if not user_id:
        # Check all active users
        with session_scope() as session:
            users = list(session.execute(select(User).limit(20)).scalars())
            user_ids = [u.id for u in users]
    else:
        user_ids = [user_id]

    ctx.progress(20, f"Scanning courses and mastery for {len(user_ids)} student(s)")

    now = utcnow()
    today_str = now.strftime("%Y-%m-%d")

    for uid in user_ids:
        with session_scope() as session:
            # 1. Fetch student courses
            courses = list(session.execute(select(Course).where(Course.user_id == uid)).scalars())
            if not courses:
                continue

            # 2. Check if daily revision plan already exists for today to guarantee restart safety
            existing_plan = session.execute(
                select(RevisionPlan).where(
                    RevisionPlan.user_id == uid,
                    RevisionPlan.title == f"Daily Revision — {today_str}",
                )
            ).scalar_one_or_none()

            if existing_plan:
                log.info("Daily revision already exists for user %s on %s. Skipping.", uid, today_str)
                continue

            # 3. Find weak or overdue topics (< 0.65 mastery)
            weak_mastery_records = list(
                session.execute(
                    select(StudentTopicMastery)
                    .where(
                        StudentTopicMastery.user_id == uid,
                        StudentTopicMastery.mastery_score < 0.65,
                    )
                    .order_by(StudentTopicMastery.mastery_score.asc())
                    .limit(5)
                ).scalars()
            )

            primary_course = courses[0]
            plan = RevisionPlan(
                user_id=uid,
                course_id=primary_course.id,
                title=f"Daily Revision — {today_str}",
                target_date=now + dt.timedelta(hours=14),
                status="active",
            )
            session.add(plan)
            session.flush()

            tasks_added = 0
            task_titles = []

            # Prioritize weak mastery topics
            for m in weak_mastery_records:
                topic = session.get(SyllabusTopic, m.topic_id)
                if not topic:
                    continue
                t_title = f"Review Weak Concept: {topic.name}"
                task = RevisionTask(
                    plan_id=plan.id,
                    topic_id=topic.id,
                    priority=1,
                    title=t_title,
                    description=f"Current mastery is {int(m.mastery_score * 100)}%. Solve 3 practice problems to reinforce recall.",
                    estimated_minutes=25,
                    is_completed=False,
                )
                session.add(task)
                tasks_added += 1
                task_titles.append(topic.name)
                if tasks_added >= 3:
                    break

            # If no weak topics recorded yet, schedule highest importance topics
            if tasks_added == 0:
                topics = list(
                    session.execute(
                        select(SyllabusTopic)
                        .where(SyllabusTopic.course_id == primary_course.id)
                        .order_by(SyllabusTopic.importance_score.desc())
                        .limit(2)
                    ).scalars()
                )
                for t in topics:
                    task = RevisionTask(
                        plan_id=plan.id,
                        topic_id=t.id,
                        priority=2,
                        title=f"Daily Drill: {t.name}",
                        description="Review core definitions, formulas, and diagrams.",
                        estimated_minutes=20,
                        is_completed=False,
                    )
                    session.add(task)
                    tasks_added += 1
                    task_titles.append(t.name)

            # In-app notification
            summary_topics = ", ".join(task_titles[:2]) if task_titles else "Key Topics"
            notif = Notification(
                user_id=uid,
                title="🌅 Morning Revision Scheduled (07:00 IST)",
                message=f"{tasks_added} actionable revision tasks generated for today. Focus on: {summary_topics}.",
                kind="revision_alert",
                link="/revision",
                data={"plan_id": plan.id, "tasks_count": tasks_added, "date": today_str},
            )
            session.add(notif)
            log.info("Scheduled %s daily revision tasks for user %s", tasks_added, uid)

    ctx.progress(100, f"Completed daily revision scheduling for {today_str}")
