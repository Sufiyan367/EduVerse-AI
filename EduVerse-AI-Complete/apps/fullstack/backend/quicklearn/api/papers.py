"""Previous Paper Intelligence & Analytics API for EduVerse AI."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db.academic_models import (
    Course,
    CourseUnit,
    ExamQuestion,
    PreviousPaper,
    QuestionTopicLink,
    SyllabusTopic,
)
from ..db.models import Segment, Source, User
from ..db.session import get_db
from ..providers.llm.ollama import call_ollama_text

log = logging.getLogger(__name__)

router = APIRouter(prefix="/courses/{course_id}/papers", tags=["papers"])


class CreatePaperRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    exam_term: str = Field(default="End-Sem", max_length=64)
    exam_year: int = Field(default=2024, ge=2000, le=2050)
    total_marks: float = Field(default=70.0, ge=1.0)
    duration_minutes: int = Field(default=150, ge=10)
    source_id: int | None = None


class ExtractPaperQuestionsRequest(BaseModel):
    paper_id: int
    source_id: int | None = None
    raw_text: str | None = None


@router.get("")
def list_papers(
    course_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    papers = db.query(PreviousPaper).filter(
        PreviousPaper.course_id == course_id,
        PreviousPaper.user_id == user.id,
    ).order_by(PreviousPaper.exam_year.desc()).all()

    result = []
    for p in papers:
        q_count = db.query(func.count(ExamQuestion.id)).filter(ExamQuestion.paper_id == p.id).scalar() or 0
        result.append({
            "id": p.id,
            "title": p.title,
            "exam_term": p.exam_term,
            "exam_year": p.exam_year,
            "total_marks": p.total_marks,
            "duration_minutes": p.duration_minutes,
            "question_count": q_count,
            "source_id": p.source_id,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
def create_paper(
    course_id: int,
    req: CreatePaperRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    paper = PreviousPaper(
        course_id=course_id,
        user_id=user.id,
        title=req.title.strip(),
        exam_term=req.exam_term.strip(),
        exam_year=req.exam_year,
        total_marks=req.total_marks,
        duration_minutes=req.duration_minutes,
        source_id=req.source_id,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    return {"id": paper.id, "title": paper.title, "exam_year": paper.exam_year}


@router.get("/{paper_id}")
def get_paper_detail(
    course_id: int,
    paper_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    paper = db.query(PreviousPaper).filter(
        PreviousPaper.id == paper_id,
        PreviousPaper.course_id == course_id,
        PreviousPaper.user_id == user.id,
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    questions = db.query(ExamQuestion).filter(ExamQuestion.paper_id == paper.id).order_by(ExamQuestion.id).all()
    q_data = []
    for q in questions:
        links = db.query(QuestionTopicLink, SyllabusTopic).join(
            SyllabusTopic, QuestionTopicLink.topic_id == SyllabusTopic.id
        ).filter(QuestionTopicLink.question_id == q.id).all()

        q_data.append({
            "id": q.id,
            "question_number": q.question_number,
            "question_text": q.question_text,
            "marks": q.marks,
            "bloom_level": q.bloom_level,
            "frequency_count": q.frequency_count,
            "topics": [{"topic_id": t[1].id, "topic_name": t[1].name} for t in links],
        })

    return {
        "id": paper.id,
        "title": paper.title,
        "exam_term": paper.exam_term,
        "exam_year": paper.exam_year,
        "total_marks": paper.total_marks,
        "duration_minutes": paper.duration_minutes,
        "questions": q_data,
    }


@router.delete("/{paper_id}")
def delete_paper(
    course_id: int,
    paper_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    paper = db.query(PreviousPaper).filter(
        PreviousPaper.id == paper_id,
        PreviousPaper.course_id == course_id,
        PreviousPaper.user_id == user.id,
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    db.delete(paper)
    db.commit()
    return {"status": "deleted", "id": str(paper_id)}


@router.post("/extract")
async def extract_paper_questions(
    course_id: int,
    req: ExtractPaperQuestionsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """AI Question Extraction & Topic Linker using local Ollama Qwen3.5:4b.

    Extracts questions, marks, and cognitive demand from university question papers.
    """
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    paper = db.query(PreviousPaper).filter(
        PreviousPaper.id == req.paper_id,
        PreviousPaper.course_id == course_id,
        PreviousPaper.user_id == user.id,
    ).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    content = ""
    source_to_use = req.source_id or paper.source_id
    if source_to_use:
        segments = db.query(Segment).filter(Segment.source_id == source_to_use).order_by(Segment.index).all()
        content = "\n".join([s.text for s in segments if s.text])[:8000]
    elif req.raw_text:
        content = req.raw_text.strip()[:8000]
    else:
        raise HTTPException(status_code=400, detail="Provide paper source_id or raw_text")

    # Fetch syllabus topics for linking
    topics = db.query(SyllabusTopic).filter(SyllabusTopic.course_id == course_id).all()
    topic_list_str = ", ".join([f'"{t.name}"' for t in topics[:40]])

    prompt = f"""You are an expert exam question extractor for university engineering courses.
Extract the exam questions from the past exam paper text below.
For each question, specify:
1. question_number (e.g. "Q1(a)", "Q2(b)")
2. question_text (complete question statement)
3. marks (numeric value, e.g. 5.0, 7.0, 10.0)
4. bloom_level ("Remember", "Understand", "Apply", "Analyze", "Evaluate")
5. matched_topic (pick the closest matching topic from this list: [{topic_list_str}])

Return ONLY valid JSON matching this exact structure:
{{
  "questions": [
    {{
      "question_number": "Q1(a)",
      "question_text": "Explain the architecture of...",
      "marks": 5.0,
      "bloom_level": "Understand",
      "matched_topic": "Topic name"
    }}
  ]
}}

Exam Paper Text:
{content}
"""
    try:
        response_text = await call_ollama_text(prompt, model="qwen3.5:4b", temperature=0.1)
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start != -1 and json_end != -1:
            data = json.loads(response_text[json_start:json_end])
        else:
            raise ValueError("No JSON detected in response")

        extracted_questions = data.get("questions", [])
        saved = 0
        topic_lookup = {t.name.lower(): t.id for t in topics}

        for q_item in extracted_questions:
            q_text = str(q_item.get("question_text", "")).strip()
            if not q_text:
                continue
            q_num = str(q_item.get("question_number", f"Q{saved+1}"))[:32]
            marks = float(q_item.get("marks", 5.0))
            bloom = str(q_item.get("bloom_level", "Understand"))[:32]

            eq = ExamQuestion(
                paper_id=paper.id,
                question_number=q_num,
                question_text=q_text,
                marks=marks,
                bloom_level=bloom,
                frequency_count=1,
            )
            db.add(eq)
            db.flush()

            matched_name = str(q_item.get("matched_topic", "")).lower()
            matched_id = topic_lookup.get(matched_name)
            if not matched_id and topics:
                # Fallback: substring match
                for t in topics:
                    if t.name.lower() in q_text.lower() or any(w in t.name.lower() for w in q_text.lower().split() if len(w) > 4):
                        matched_id = t.id
                        break

            if matched_id:
                link = QuestionTopicLink(question_id=eq.id, topic_id=matched_id, relevance_score=1.0)
                db.add(link)
                # Boost topic importance score
                topic_rec = db.query(SyllabusTopic).get(matched_id)
                if topic_rec:
                    topic_rec.importance_score += 0.5

            saved += 1

        db.commit()
        return {"status": "success", "questions_extracted": saved}
    except Exception as exc:
        log.warning("AI question extraction degraded: %s", exc)
        return {"status": "error", "message": str(exc)}


@router.get("/analytics/overview")
def get_paper_analytics(
    course_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Previous Paper Intelligence: frequency rankings, unit weightage, and high-yield predictions."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    papers = db.query(PreviousPaper).filter(PreviousPaper.course_id == course_id, PreviousPaper.user_id == user.id).all()
    paper_ids = [p.id for p in papers]

    questions = db.query(ExamQuestion).filter(ExamQuestion.paper_id.in_(paper_ids)).all() if paper_ids else []

    # 1. Topic frequency & marks
    topics = db.query(SyllabusTopic).filter(SyllabusTopic.course_id == course_id).all()
    topic_stats = []
    for t in topics:
        q_count = (
            db.query(func.count(QuestionTopicLink.id))
            .join(ExamQuestion, QuestionTopicLink.question_id == ExamQuestion.id)
            .filter(QuestionTopicLink.topic_id == t.id, ExamQuestion.paper_id.in_(paper_ids))
            .scalar() or 0
        ) if paper_ids else 0

        total_marks = (
            db.query(func.sum(ExamQuestion.marks))
            .join(QuestionTopicLink, QuestionTopicLink.question_id == ExamQuestion.id)
            .filter(QuestionTopicLink.topic_id == t.id, ExamQuestion.paper_id.in_(paper_ids))
            .scalar() or 0.0
        ) if paper_ids else 0.0

        topic_stats.append({
            "topic_id": t.id,
            "topic_name": t.name,
            "unit_id": t.unit_id,
            "bloom_level": t.bloom_level,
            "importance_score": round(t.importance_score, 2),
            "frequency": q_count,
            "total_marks_tested": float(total_marks),
            "exam_yield": "High" if q_count >= 2 or t.importance_score > 1.5 else ("Medium" if q_count == 1 else "Standard"),
        })

    # Sort by frequency and importance
    topic_stats.sort(key=lambda x: (x["frequency"], x["importance_score"]), reverse=True)

    # 2. Bloom distribution
    bloom_counts: dict[str, int] = {}
    for q in questions:
        lvl = q.bloom_level or "Understand"
        bloom_counts[lvl] = bloom_counts.get(lvl, 0) + 1

    # 3. Unit weightage distribution
    units = db.query(CourseUnit).filter(CourseUnit.course_id == course_id).order_by(CourseUnit.unit_number).all()
    unit_distribution = []
    for u in units:
        u_topics = [t.id for t in u.topics]
        u_marks = (
            db.query(func.sum(ExamQuestion.marks))
            .join(QuestionTopicLink, QuestionTopicLink.question_id == ExamQuestion.id)
            .filter(QuestionTopicLink.topic_id.in_(u_topics), ExamQuestion.paper_id.in_(paper_ids))
            .scalar() or 0.0
        ) if u_topics and paper_ids else 0.0

        unit_distribution.append({
            "unit_number": u.unit_number,
            "unit_title": u.title,
            "syllabus_weightage": u.weightage_percent,
            "past_paper_marks": float(u_marks),
        })

    return {
        "course_id": course.id,
        "course_name": course.name,
        "total_papers_analyzed": len(papers),
        "total_questions_cataloged": len(questions),
        "high_yield_topics": topic_stats[:10],
        "all_topic_frequencies": topic_stats,
        "bloom_distribution": bloom_counts,
        "unit_distribution": unit_distribution,
    }
