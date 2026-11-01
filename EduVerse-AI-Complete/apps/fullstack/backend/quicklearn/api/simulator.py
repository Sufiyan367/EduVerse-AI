"""Exam Simulator API: Realistic university timed exam simulations."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db.academic_models import (
    AnswerAttempt,
    AssessmentQuestion,
    Course,
    CourseUnit,
    ExamQuestion,
    ExamSession,
    GradingFeedback,
    PreviousPaper,
    QuestionTopicLink,
    SyllabusTopic,
)
from ..db.models import User
from ..db.session import get_db
from ..db.types import utcnow

log = logging.getLogger(__name__)

router = APIRouter(prefix="/simulator", tags=["simulator"])


class GenerateExamRequest(BaseModel):
    course_id: int
    title: str = Field(default="In-Sem / Mid-Term Simulation 50M")
    max_score: float = Field(default=50.0, ge=10.0, le=100.0)
    question_count: int = Field(default=5, ge=2, le=20)


class SubmitAnswerItem(BaseModel):
    question_id: int
    student_answer: str = Field(..., min_length=1)


class SubmitExamRequest(BaseModel):
    answers: list[SubmitAnswerItem]


@router.post("/courses/{course_id}/generate", status_code=status.HTTP_201_CREATED)
def generate_simulation(
    course_id: int,
    req: GenerateExamRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Generate a realistic simulated exam session across units according to syllabus weights."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    session = ExamSession(
        course_id=course_id,
        user_id=user.id,
        title=req.title.strip(),
        max_score=req.max_score,
        status="in_progress",
        started_at=utcnow(),
    )
    db.add(session)
    db.flush()

    # Find syllabus topics and any past questions
    units = db.query(CourseUnit).filter(CourseUnit.course_id == course_id).order_by(CourseUnit.unit_number).all()
    past_questions = (
        db.query(ExamQuestion)
        .join(PreviousPaper, ExamQuestion.paper_id == PreviousPaper.id)
        .filter(PreviousPaper.course_id == course_id)
        .all()
    )

    questions_created = 0
    marks_per_q = round(req.max_score / req.question_count, 1)

    # Use past questions if available, else construct structured questions from topics
    if past_questions:
        selected_past = past_questions[:req.question_count]
        for idx, pq in enumerate(selected_past):
            link = db.query(QuestionTopicLink).filter(QuestionTopicLink.question_id == pq.id).first()
            topic_id = link.topic_id if link else None

            aq = AssessmentQuestion(
                session_id=session.id,
                topic_id=topic_id,
                question_text=pq.question_text,
                ideal_answer=None,
                marks=pq.marks or marks_per_q,
                question_order=idx + 1,
            )
            db.add(aq)
            questions_created += 1

    # Fill remaining from units & syllabus topics
    if questions_created < req.question_count and units:
        all_topics = db.query(SyllabusTopic).filter(SyllabusTopic.course_id == course_id).all()
        for idx in range(questions_created, req.question_count):
            topic = all_topics[idx % len(all_topics)] if all_topics else None
            t_name = topic.name if topic else f"Unit Module {(idx % len(units)) + 1}"
            bloom = topic.bloom_level if topic else "Understand"

            if bloom in ("Apply", "Analyze"):
                q_text = f"Analyze the working principles of {t_name}. Provide system architecture, mathematical derivations or step-by-step algorithms, and justify implementation tradeoffs."
            else:
                q_text = f"Explain the fundamental concepts of {t_name} with relevant block diagrams, core definitions, and industrial use-cases."

            aq = AssessmentQuestion(
                session_id=session.id,
                topic_id=topic.id if topic else None,
                question_text=q_text,
                ideal_answer=None,
                marks=marks_per_q,
                question_order=idx + 1,
            )
            db.add(aq)
            questions_created += 1

    db.commit()
    return {
        "session_id": session.id,
        "title": session.title,
        "max_score": session.max_score,
        "question_count": questions_created,
        "started_at": session.started_at.isoformat(),
    }


@router.get("/sessions/{session_id}")
def get_session_detail(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
        ExamSession.user_id == user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Exam session not found")

    questions = db.query(AssessmentQuestion).filter(
        AssessmentQuestion.session_id == session.id
    ).order_by(AssessmentQuestion.question_order).all()

    q_list = []
    for q in questions:
        attempt = db.query(AnswerAttempt).filter(
            AnswerAttempt.session_id == session.id,
            AnswerAttempt.question_id == q.id,
        ).first()

        feedback = None
        if attempt and attempt.feedback:
            feedback = {
                "score_awarded": attempt.feedback.score_awarded,
                "evaluator_model": attempt.feedback.evaluator_model,
                "criterion_scores": attempt.feedback.criterion_scores,
                "strengths": attempt.feedback.strengths,
                "weaknesses": attempt.feedback.weaknesses,
                "suggestions": attempt.feedback.suggestions,
                "graded_at": attempt.feedback.graded_at.isoformat(),
            }

        topic = db.query(SyllabusTopic).get(q.topic_id) if q.topic_id else None

        q_list.append({
            "id": q.id,
            "order": q.question_order,
            "question_text": q.question_text,
            "marks": q.marks,
            "topic_id": q.topic_id,
            "topic_name": topic.name if topic else "General Course Concept",
            "student_answer": attempt.student_answer if attempt else None,
            "feedback": feedback,
        })

    return {
        "id": session.id,
        "course_id": session.course_id,
        "title": session.title,
        "status": session.status,
        "total_score": session.total_score,
        "max_score": session.max_score,
        "started_at": session.started_at.isoformat(),
        "submitted_at": session.submitted_at.isoformat() if session.submitted_at else None,
        "questions": q_list,
    }


@router.post("/sessions/{session_id}/submit")
def submit_exam_answers(
    session_id: int,
    req: SubmitExamRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
        ExamSession.user_id == user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Exam session not found")

    submitted_count = 0
    for ans in req.answers:
        attempt = db.query(AnswerAttempt).filter(
            AnswerAttempt.session_id == session.id,
            AnswerAttempt.question_id == ans.question_id,
            AnswerAttempt.user_id == user.id,
        ).first()

        if not attempt:
            attempt = AnswerAttempt(
                session_id=session.id,
                question_id=ans.question_id,
                user_id=user.id,
                student_answer=ans.student_answer.strip(),
                submitted_at=utcnow(),
            )
            db.add(attempt)
        else:
            attempt.student_answer = ans.student_answer.strip()
            attempt.submitted_at = utcnow()
        submitted_count += 1

    session.status = "submitted"
    session.submitted_at = utcnow()
    try:
        from ..automation import trigger_event
        trigger_event("exam_session_completed", {"session_id": session.id, "user_id": user.id}, user_id=user.id)
    except Exception as exc:
        log.warning("Failed to trigger exam_session_completed: %s", exc)
    db.commit()
    return {"status": "submitted", "session_id": session.id, "answers_saved": submitted_count}


@router.get("/history")
def get_exam_history(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    sessions = (
        db.query(ExamSession, Course.name)
        .join(Course, ExamSession.course_id == Course.id)
        .filter(ExamSession.user_id == user.id)
        .order_by(ExamSession.started_at.desc())
        .limit(20)
        .all()
    )

    return [
        {
            "id": s[0].id,
            "course_id": s[0].course_id,
            "course_name": s[1],
            "title": s[0].title,
            "status": s[0].status,
            "total_score": s[0].total_score,
            "max_score": s[0].max_score,
            "percentage": round((s[0].total_score / s[0].max_score) * 100, 1) if s[0].total_score is not None else None,
            "started_at": s[0].started_at.isoformat(),
            "submitted_at": s[0].submitted_at.isoformat() if s[0].submitted_at else None,
        }
        for s in sessions
    ]
