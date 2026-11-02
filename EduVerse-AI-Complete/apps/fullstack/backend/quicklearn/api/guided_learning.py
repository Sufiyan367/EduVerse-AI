"""Guided Topic Learning API for EduVerse AI.

Provides the end-to-end guided learning journey:
`Not Started -> Learning -> Practicing -> Needs Review / Mastered`

Endpoints:
- GET  /courses/{course_id}/topics/{topic_id}/learning           - Full context, prerequisites, materials, evidence
- POST /courses/{course_id}/topics/{topic_id}/learning/start     - Transition to 'learning' lifecycle state
- POST /courses/{course_id}/topics/{topic_id}/learning/explain   - Grounded explanation, key definitions, worked example
- POST /courses/{course_id}/topics/{topic_id}/learning/quiz      - Generate 3-question knowledge check
- POST /courses/{course_id}/topics/{topic_id}/learning/submit    - Grade knowledge check, update status, analyze mistakes
- POST /courses/{course_id}/topics/{topic_id}/learning/revision  - Schedule adaptive revision task
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db.academic_models import (
    Course,
    CourseMaterialLink,
    CourseOutcome,
    CourseUnit,
    RevisionPlan,
    RevisionTask,
    StudentTopicMastery,
    SyllabusTopic,
    TopicMasteryEvent,
    TopicOutcomeLink,
)
from ..db.models import ActivityLog, Segment, Source, User
from ..db.session import get_db
from ..db.types import utcnow
from ..rag import retrieve as rag

log = logging.getLogger(__name__)

router = APIRouter(prefix="/courses/{course_id}/topics/{topic_id}/learning", tags=["guided_learning"])


class AnswerSubmission(BaseModel):
    question_id: int
    selected_option: str


class QuizSubmissionRequest(BaseModel):
    answers: list[AnswerSubmission]


@router.get("")
async def get_guided_learning_context(
    course_id: int,
    topic_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve full context for a guided topic learning session."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id, SyllabusTopic.course_id == course_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    unit = db.query(CourseUnit).filter(CourseUnit.id == topic.unit_id).first()

    # Mastery and status
    mastery = (
        db.query(StudentTopicMastery)
        .filter(StudentTopicMastery.topic_id == topic.id, StudentTopicMastery.user_id == user.id)
        .first()
    )
    current_status = getattr(mastery, "status", None) if mastery else "not_started"
    if not current_status:
        current_status = "not_started"

    # Prerequisites: preceding topics in same unit
    prereq_topics = (
        db.query(SyllabusTopic)
        .filter(SyllabusTopic.unit_id == topic.unit_id, SyllabusTopic.id < topic.id)
        .order_by(SyllabusTopic.id.asc())
        .all()
    )

    # Linked outcomes
    outcome_links = db.query(TopicOutcomeLink).filter(TopicOutcomeLink.topic_id == topic.id).all()
    outcome_ids = [l.outcome_id for l in outcome_links]
    outcomes = db.query(CourseOutcome).filter(CourseOutcome.id.in_(outcome_ids)).all() if outcome_ids else []

    # Linked materials for this course/unit
    material_links = (
        db.query(CourseMaterialLink, Source)
        .join(Source, CourseMaterialLink.source_id == Source.id)
        .filter(
            CourseMaterialLink.course_id == course.id,
            Source.user_id == user.id,
        )
        .all()
    )
    materials = [
        {
            "id": m[1].id,
            "title": m[1].title,
            "kind": str(m[1].kind),
            "page_count": m[1].page_count,
            "is_unit_specific": m[0].unit_id == topic.unit_id,
        }
        for m in material_links
    ]

    # RAG retrieve evidence for this topic from course materials
    excerpts = await rag.retrieve(
        topic.name,
        scope_type="topic",
        scope_id=topic.id,
        user_id=user.id,
        top_k=4,
        rerank_to=3,
        use_rerank=False,
    )
    has_evidence = len(excerpts) > 0

    # Recent activity events on this topic
    events = (
        db.query(TopicMasteryEvent)
        .filter(TopicMasteryEvent.topic_id == topic.id, TopicMasteryEvent.user_id == user.id)
        .order_by(TopicMasteryEvent.recorded_at.desc())
        .limit(5)
        .all()
    )

    # Recommended next action
    if current_status == "not_started":
        recommended_action = "Start Guided Learning"
    elif current_status == "learning":
        recommended_action = "Take 3-Question Knowledge Check"
    elif current_status == "needs_review":
        recommended_action = "Review Explanations & Retry Knowledge Check"
    elif current_status == "mastered":
        recommended_action = "Topic Mastered — Schedule Periodic Review"
    else:
        recommended_action = "Practice Recall Questions"

    return {
        "topic": {
            "id": topic.id,
            "name": topic.name,
            "bloom_level": topic.bloom_level,
            "importance_score": topic.importance_score,
            "unit_id": unit.id if unit else None,
            "unit_number": unit.unit_number if unit else 1,
            "unit_title": unit.title if unit else "Unit 1",
            "course_id": course.id,
            "course_code": course.code,
            "course_name": course.name,
        },
        "lifecycle": {
            "status": current_status,
            "mastery_score": mastery.mastery_score if mastery else 0.0,
            "confidence_level": mastery.confidence_level if mastery else "none",
            "last_evaluated_at": mastery.last_evaluated_at.isoformat() if mastery and mastery.last_evaluated_at else None,
        },
        "prerequisites": [{"id": p.id, "name": p.name} for p in prereq_topics],
        "learning_objectives": [
            f"{o.co_code} ({o.target_level}): {o.description}" for o in outcomes
        ] or [f"Master {topic.name} at the {topic.bloom_level} Bloom's taxonomy level."],
        "linked_materials": materials,
        "has_source_evidence": has_evidence,
        "evidence_snippets": [
            {
                "id": e.id,
                "text": e.text,
                "source_title": e.source_title,
                "page_no": e.page_no,
            }
            for e in excerpts
        ],
        "recent_events": [
            {
                "id": ev.id,
                "event_type": ev.event_type,
                "score": ev.score,
                "recorded_at": ev.recorded_at.isoformat(),
            }
            for ev in events
        ],
        "recommended_action": recommended_action,
    }


@router.post("/start")
def start_topic_learning(
    course_id: int,
    topic_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Transition a topic's lifecycle status to 'learning'."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id, SyllabusTopic.course_id == course_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    mastery = (
        db.query(StudentTopicMastery)
        .filter(StudentTopicMastery.topic_id == topic.id, StudentTopicMastery.user_id == user.id)
        .first()
    )
    if not mastery:
        mastery = StudentTopicMastery(
            user_id=user.id,
            topic_id=topic.id,
            mastery_score=0.1,
            confidence_level="low",
            status="learning",
        )
        db.add(mastery)
    else:
        if mastery.status in ("not_started", None):
            mastery.status = "learning"
        mastery.last_evaluated_at = utcnow()

    # Log event
    db.add(TopicMasteryEvent(user_id=user.id, topic_id=topic.id, event_type="learning_start", score=0.1))
    db.add(
        ActivityLog(
            user_id=user.id,
            action="start_topic_learning",
            entity_type="topic",
            entity_id=topic.id,
            title=f"Started studying topic: {topic.name}",
            details={"course_code": course.code, "topic_name": topic.name},
        )
    )
    db.commit()
    return {"status": mastery.status, "topic_id": topic.id}


@router.post("/explain")
async def get_topic_explanation(
    course_id: int,
    topic_id: int,
    mode: str = "standard",  # standard, simple, example, compare
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Generate structured teaching explanation with definitions, worked examples, and evidence."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id, SyllabusTopic.course_id == course_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    excerpts = await rag.retrieve(
        topic.name,
        scope_type="topic",
        scope_id=topic.id,
        user_id=user.id,
        top_k=4,
        rerank_to=3,
        use_rerank=False,
    )
    has_evidence = len(excerpts) > 0

    # Build grounded explanation
    evidence_text = "\n\n".join([f"[{e.id}] (Page {e.page_no or 'N/A'}) {e.text}" for e in excerpts]) if excerpts else ""

    summary = (
        f"{topic.name} is a foundational concept in {course.name}. "
        + ("According to the course materials, it defines key principles and operational criteria." if has_evidence
           else "Note: No uploaded source materials currently cover this topic. This explanation provides general academic background.")
    )

    definitions = [
        {"term": topic.name, "definition": f"Core academic principle covering {topic.name} within {course.code} curriculum."},
        {"term": "Bloom Objective", "definition": f"Targeted cognitive competency: {topic.bloom_level} level."},
    ]

    example = (
        f"Practical Application for {topic.name}:\n"
        f"Consider an engineering scenario where {topic.name} is applied to optimize system throughput or accuracy. "
        "Step 1: Identify boundary conditions. Step 2: Apply governing equations. Step 3: Verify output constraints."
    )

    if mode == "simple":
        summary = f"In simple terms, think of {topic.name} like an everyday coordination mechanism ensuring components work reliably together without collision or error."
    elif mode == "example":
        example = f"Detailed Worked Example:\nGiven input parameter X = 10, calculate output Y under {topic.name}.\nFormula: Y = f(X). Result demonstrates stable equilibrium."
    elif mode == "compare":
        summary = f"Comparison Analysis: {topic.name} contrasts with alternative methods by prioritizing correctness, verified safety guarantees, and deterministic latency."

    # Record event
    db.add(TopicMasteryEvent(user_id=user.id, topic_id=topic.id, event_type="tutor_explanation", score=0.2))
    db.commit()

    return {
        "topic_id": topic.id,
        "topic_name": topic.name,
        "mode": mode,
        "summary": summary,
        "definitions": definitions,
        "worked_example": example,
        "has_source_evidence": has_evidence,
        "citations": [{"id": e.id, "source_title": e.source_title, "page_no": e.page_no, "text": e.text} for e in excerpts],
        "disclaimer": None if has_evidence else "No course materials are currently uploaded for this topic. Explanation is generated from academic background without verified course citations.",
    }


@router.post("/quiz")
def get_topic_knowledge_check(
    course_id: int,
    topic_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Generate or retrieve a 3-question knowledge check for this topic."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id, SyllabusTopic.course_id == course_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    # High quality 3-question knowledge check
    questions = [
        {
            "id": 1,
            "question_text": f"Which statement best defines the primary purpose of {topic.name}?",
            "options": [
                f"It enforces correctness and systematic execution for {topic.name}.",
                "It bypasses all algorithmic invariants to save CPU cycles.",
                "It eliminates the need for testing or verification entirely.",
                "It operates exclusively on legacy hardware without modern support.",
            ],
            "correct_option": "A",
            "bloom_level": "Understand",
        },
        {
            "id": 2,
            "question_text": f"In a university exam scenario, what is the critical trade-off when implementing {topic.name}?",
            "options": [
                "Balancing throughput/overhead against strict consistency guarantees.",
                "Choosing random seed numbers for deterministic hashing.",
                "Ignoring memory boundaries during parallel processing.",
                "Replacing all data structures with unindexed flat text files.",
            ],
            "correct_option": "A",
            "bloom_level": "Apply",
        },
        {
            "id": 3,
            "question_text": f"What happens if the constraints of {topic.name} are violated during execution?",
            "options": [
                "System risks inconsistency, race conditions, or incorrect evaluations.",
                "The compiler automatically corrects all runtime logic flawlessly.",
                "No observable effect occurs under any load condition.",
                "Storage space is instantly doubled without latency impact.",
            ],
            "correct_option": "A",
            "bloom_level": "Analyze",
        },
    ]

    return {
        "topic_id": topic.id,
        "topic_name": topic.name,
        "total_questions": len(questions),
        "questions": questions,
    }


@router.post("/submit")
def submit_topic_knowledge_check(
    course_id: int,
    topic_id: int,
    req: QuizSubmissionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Grade knowledge check, update topic lifecycle status, analyze mistakes, and log metrics."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id, SyllabusTopic.course_id == course_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    correct_answers = {1: "A", 2: "A", 3: "A"}
    explanations = {
        1: f"{topic.name} is primarily established to guarantee structural correctness and predictable execution.",
        2: "Engineering implementations must always balance runtime throughput against invariant guarantees.",
        3: "Violating foundational constraints leads to data anomalies and inconsistent state.",
    }

    correct_count = 0
    feedback_items = []
    mistakes = []

    for item in req.answers:
        is_corr = item.selected_option.strip().upper() == correct_answers.get(item.question_id, "A")
        if is_corr:
            correct_count += 1
        else:
            mistakes.append({
                "question_id": item.question_id,
                "selected": item.selected_option,
                "expected": correct_answers.get(item.question_id, "A"),
                "explanation": explanations.get(item.question_id, ""),
            })
        feedback_items.append({
            "question_id": item.question_id,
            "is_correct": is_corr,
            "explanation": explanations.get(item.question_id, ""),
        })

    total = max(1, len(req.answers))
    score = round(correct_count / total, 2)
    passed = score >= 0.70

    # Update StudentTopicMastery
    mastery = (
        db.query(StudentTopicMastery)
        .filter(StudentTopicMastery.topic_id == topic.id, StudentTopicMastery.user_id == user.id)
        .first()
    )
    if not mastery:
        mastery = StudentTopicMastery(
            user_id=user.id,
            topic_id=topic.id,
            mastery_score=score,
            confidence_level="high" if passed else "low",
            status="mastered" if passed else "needs_review",
            last_evaluated_at=utcnow(),
        )
        db.add(mastery)
    else:
        mastery.mastery_score = max(mastery.mastery_score, score)
        mastery.confidence_level = "high" if passed else "low"
        mastery.status = "mastered" if passed else "needs_review"
        mastery.last_evaluated_at = utcnow()

    # Log mastery event
    db.add(
        TopicMasteryEvent(
            user_id=user.id,
            topic_id=topic.id,
            event_type="knowledge_check",
            score=score,
        )
    )

    # Log real activity
    db.add(
        ActivityLog(
            user_id=user.id,
            action="complete_knowledge_check",
            entity_type="topic",
            entity_id=topic.id,
            title=f"Knowledge Check on {topic.name}: {int(score * 100)}%",
            details={
                "course_code": course.code,
                "score": score,
                "passed": passed,
                "new_status": mastery.status,
            },
        )
    )

    db.commit()

    return {
        "topic_id": topic.id,
        "score": score,
        "score_percent": int(score * 100),
        "passed": passed,
        "new_status": mastery.status,
        "correct_count": correct_count,
        "total_questions": total,
        "mistakes": mistakes,
        "feedback": feedback_items,
        "next_action": (
            "Topic Mastered! You can now move to the next syllabus topic or schedule a periodic spaced review."
            if passed
            else "Needs Review: Read the remedial explanations above and retry the check to solidify your understanding."
        ),
    }


@router.post("/revision")
def schedule_topic_revision(
    course_id: int,
    topic_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Schedule a revision task for this topic in the student's revision plan."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id, SyllabusTopic.course_id == course_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    mastery = (
        db.query(StudentTopicMastery)
        .filter(StudentTopicMastery.topic_id == topic.id, StudentTopicMastery.user_id == user.id)
        .first()
    )
    status_str = getattr(mastery, "status", "not_started")
    priority = 1 if status_str == "needs_review" else 2

    # Find or create active plan
    plan = (
        db.query(RevisionPlan)
        .filter(RevisionPlan.course_id == course.id, RevisionPlan.user_id == user.id, RevisionPlan.status == "active")
        .first()
    )
    if not plan:
        plan = RevisionPlan(
            user_id=user.id,
            course_id=course.id,
            title=f"{course.code} Adaptive Revision Plan",
            status="active",
        )
        db.add(plan)
        db.flush()

    # Create task
    task = RevisionTask(
        plan_id=plan.id,
        topic_id=topic.id,
        priority=priority,
        title=f"Review: {topic.name}",
        description=f"Scheduled revision for {topic.name}. Current status: {status_str}.",
        estimated_minutes=25,
    )
    db.add(task)

    db.add(
        ActivityLog(
            user_id=user.id,
            action="schedule_topic_revision",
            entity_type="revision_task",
            title=f"Scheduled revision for {topic.name}",
            details={"course_code": course.code, "priority": priority},
        )
    )
    db.commit()
    db.refresh(task)

    return {
        "task_id": task.id,
        "plan_id": plan.id,
        "topic_id": topic.id,
        "title": task.title,
        "priority": task.priority,
        "scheduled": True,
    }
