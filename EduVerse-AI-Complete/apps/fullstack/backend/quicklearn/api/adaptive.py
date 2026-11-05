"""Adaptive Learning, Mastery Graph & Remediation Planner API for EduVerse AI."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db.academic_models import (
    Course,
    CourseUnit,
    RemediationAttempt,
    RevisionPlan,
    RevisionTask,
    StudentTopicMastery,
    SyllabusTopic,
    TopicMasteryEvent,
)
from ..db.models import User
from ..db.session import get_db
from ..db.types import utcnow

log = logging.getLogger(__name__)

router = APIRouter(prefix="/adaptive", tags=["adaptive"])


class GeneratePlanRequest(BaseModel):
    title: str = Field(default="Adaptive Exam Target Plan", min_length=2, max_length=255)
    target_date: dt.datetime | None = None


class RemediationRequest(BaseModel):
    action_type: str = Field(default="flashcards")  # flashcards, mini_quiz, rag_notes
    delta: float = Field(default=0.15, ge=0.01, le=1.0)


@router.get("/courses/{course_id}/mastery")
def get_course_mastery_profile(
    course_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve full student mastery graph across all units and topics."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    units = db.query(CourseUnit).filter(CourseUnit.course_id == course_id).order_by(CourseUnit.unit_number).all()

    unit_profiles = []
    all_topics_data = []
    total_score_sum = 0.0
    total_topics = 0

    weak_areas = []
    strong_areas = []

    for u in units:
        topics = db.query(SyllabusTopic).filter(SyllabusTopic.unit_id == u.id).all()
        u_topics = []
        u_score_sum = 0.0

        for t in topics:
            total_topics += 1
            mastery = db.query(StudentTopicMastery).filter(
                StudentTopicMastery.user_id == user.id,
                StudentTopicMastery.topic_id == t.id,
            ).first()

            score = mastery.mastery_score if mastery else 0.0
            conf = mastery.confidence_level if mastery else "low"
            u_score_sum += score
            total_score_sum += score

            topic_info = {
                "id": t.id,
                "name": t.name,
                "bloom_level": t.bloom_level,
                "importance_score": round(t.importance_score, 2),
                "mastery_score": round(score, 2),
                "confidence_level": conf,
                "last_evaluated": mastery.last_evaluated_at.isoformat() if mastery else None,
            }
            u_topics.append(topic_info)
            all_topics_data.append(topic_info)

            if score < 0.6:
                weak_areas.append(topic_info)
            elif score >= 0.8:
                strong_areas.append(topic_info)

        avg_unit_mastery = round(u_score_sum / max(1, len(topics)), 2)
        unit_profiles.append({
            "unit_number": u.unit_number,
            "unit_title": u.title,
            "average_mastery": avg_unit_mastery,
            "topics": u_topics,
        })

    overall_mastery = round(total_score_sum / max(1, total_topics), 2)

    return {
        "course_id": course.id,
        "course_name": course.name,
        "overall_mastery_percentage": round(overall_mastery * 100, 1),
        "total_topics": total_topics,
        "units": unit_profiles,
        "weak_topics_count": len(weak_areas),
        "strong_topics_count": len(strong_areas),
        "priority_gaps": sorted(weak_areas, key=lambda x: (x["mastery_score"], -x["importance_score"]))[:6],
    }


@router.post("/courses/{course_id}/plan", status_code=status.HTTP_201_CREATED)
def generate_adaptive_plan(
    course_id: int,
    req: GeneratePlanRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Generate a prioritized, adaptive revision plan targeting highest-yield weaknesses."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Mark any existing active plans as superseded
    existing_plans = db.query(RevisionPlan).filter(
        RevisionPlan.course_id == course_id,
        RevisionPlan.user_id == user.id,
        RevisionPlan.status == "active",
    ).all()
    for p in existing_plans:
        p.status = "superseded"

    new_plan = RevisionPlan(
        course_id=course_id,
        user_id=user.id,
        title=req.title.strip(),
        target_date=req.target_date or course.target_exam_date,
        status="active",
        created_at=utcnow(),
    )
    db.add(new_plan)
    db.flush()

    # Find weak topics with high importance
    topics = db.query(SyllabusTopic).filter(SyllabusTopic.course_id == course_id).all()
    prioritized = []

    for t in topics:
        mastery = db.query(StudentTopicMastery).filter(
            StudentTopicMastery.user_id == user.id,
            StudentTopicMastery.topic_id == t.id,
        ).first()
        m_score = mastery.mastery_score if mastery else 0.0

        # Priority calculation: higher importance + lower mastery = highest priority
        priority_rank = (1.0 - m_score) * 2.0 + (t.importance_score * 1.5)
        prioritized.append((t, m_score, priority_rank))

    # Sort descending by urgency
    prioritized.sort(key=lambda x: x[2], reverse=True)

    tasks_created = 0
    for idx, (top, score, _) in enumerate(prioritized[:8]):
        priority_lvl = 1 if idx < 3 else (2 if idx < 6 else 3)
        est_min = 25 if top.bloom_level == "Remember" else (40 if top.bloom_level in ("Apply", "Analyze") else 30)

        task = RevisionTask(
            plan_id=new_plan.id,
            topic_id=top.id,
            priority=priority_lvl,
            title=f"Review & Remediate: {top.name}",
            description=f"Topic has current mastery of {int(score * 100)}% and Bloom level '{top.bloom_level}'. Focus on formulas, key definitions, and practice questions.",
            estimated_minutes=est_min,
            is_completed=False,
        )
        db.add(task)
        tasks_created += 1

    db.commit()
    return {
        "plan_id": new_plan.id,
        "title": new_plan.title,
        "tasks_generated": tasks_created,
        "status": "active",
    }


@router.get("/courses/{course_id}/plan")
def get_current_plan(
    course_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    plan = db.query(RevisionPlan).filter(
        RevisionPlan.course_id == course_id,
        RevisionPlan.user_id == user.id,
        RevisionPlan.status == "active",
    ).order_by(RevisionPlan.created_at.desc()).first()

    if not plan:
        return {"has_plan": False}

    tasks = db.query(RevisionTask).filter(RevisionTask.plan_id == plan.id).order_by(RevisionTask.priority, RevisionTask.id).all()

    return {
        "has_plan": True,
        "id": plan.id,
        "title": plan.title,
        "target_date": plan.target_date.isoformat() if plan.target_date else None,
        "status": plan.status,
        "created_at": plan.created_at.isoformat(),
        "completion_rate": round((sum(1 for t in tasks if t.is_completed) / max(1, len(tasks))) * 100, 1),
        "tasks": [
            {
                "id": t.id,
                "topic_id": t.topic_id,
                "priority": t.priority,
                "title": t.title,
                "description": t.description,
                "estimated_minutes": t.estimated_minutes,
                "is_completed": t.is_completed,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            }
            for t in tasks
        ],
    }


@router.post("/tasks/{task_id}/toggle")
def toggle_task_completion(
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    task = (
        db.query(RevisionTask)
        .join(RevisionPlan, RevisionTask.plan_id == RevisionPlan.id)
        .filter(RevisionTask.id == task_id, RevisionPlan.user_id == user.id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.is_completed = not task.is_completed
    task.completed_at = utcnow() if task.is_completed else None
    db.commit()
    return {"id": task.id, "is_completed": task.is_completed}


@router.post("/tasks/{task_id}/remediate")
def remediate_task(
    task_id: int,
    req: RemediationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    task = (
        db.query(RevisionTask)
        .join(RevisionPlan, RevisionTask.plan_id == RevisionPlan.id)
        .filter(RevisionTask.id == task_id, RevisionPlan.user_id == user.id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    attempt = RemediationAttempt(
        task_id=task.id,
        user_id=user.id,
        action_type=req.action_type,
        performance_delta=req.delta,
        created_at=utcnow(),
    )
    db.add(attempt)

    # Boost student topic mastery
    if task.topic_id:
        mastery = db.query(StudentTopicMastery).filter(
            StudentTopicMastery.user_id == user.id,
            StudentTopicMastery.topic_id == task.topic_id,
        ).first()
        if mastery:
            mastery.mastery_score = min(1.0, round(mastery.mastery_score + req.delta, 2))
            mastery.confidence_level = "high" if mastery.mastery_score >= 0.75 else ("medium" if mastery.mastery_score >= 0.5 else "low")
            mastery.last_evaluated_at = utcnow()

        event = TopicMasteryEvent(
            user_id=user.id,
            topic_id=task.topic_id,
            event_type="remediation",
            score=req.delta,
            recorded_at=utcnow(),
        )
        db.add(event)

    task.is_completed = True
    task.completed_at = utcnow()
    db.commit()

    return {
        "status": "remediated",
        "task_id": task.id,
        "action_type": req.action_type,
        "delta": req.delta,
    }
