"""Syllabus Intelligence & Outcome Mapping API for EduVerse AI."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db.academic_models import (
    Course,
    CourseOutcome,
    CourseUnit,
    SyllabusTopic,
    TopicOutcomeLink,
    StudentTopicMastery,
)
from ..db.models import Segment, Source, User
from ..db.session import get_db
from ..providers.llm.ollama import call_ollama_text

log = logging.getLogger(__name__)

router = APIRouter(prefix="/courses/{course_id}/syllabus", tags=["syllabus"])


class CreateUnitRequest(BaseModel):
    unit_number: int = Field(..., ge=1, le=20)
    title: str = Field(..., min_length=2, max_length=255)
    description: str = Field(default="")
    weightage_percent: float = Field(default=16.6, ge=0.0, le=100.0)


class CreateTopicRequest(BaseModel):
    unit_id: int
    name: str = Field(..., min_length=2, max_length=255)
    bloom_level: str = Field(default="Understand", max_length=32)
    importance_score: float = Field(default=1.0, ge=0.0)
    outcome_ids: list[int] = Field(default_factory=list)


class ExtractSyllabusRequest(BaseModel):
    source_id: int | None = None
    raw_text: str | None = None


@router.get("")
def get_syllabus(
    course_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve full syllabus hierarchy: units, topics, Bloom levels, and outcome links."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    units = db.query(CourseUnit).filter(CourseUnit.course_id == course_id).order_by(CourseUnit.unit_number).all()
    outcomes = db.query(CourseOutcome).filter(CourseOutcome.course_id == course_id).all()
    co_map = {o.id: o.co_code for o in outcomes}

    units_data = []
    total_topics = 0
    for u in units:
        topics = db.query(SyllabusTopic).filter(SyllabusTopic.unit_id == u.id).order_by(SyllabusTopic.id).all()
        topics_data = []
        for t in topics:
            total_topics += 1
            linked_cos = [co_map.get(link.outcome_id, "") for link in t.outcome_links if link.outcome_id in co_map]
            m = (
                db.query(StudentTopicMastery)
                .filter(StudentTopicMastery.topic_id == t.id, StudentTopicMastery.user_id == user.id)
                .first()
            )
            st = getattr(m, "status", None) if m else "not_started"
            if not st:
                st = "not_started"
            topics_data.append({
                "id": t.id,
                "name": t.name,
                "bloom_level": t.bloom_level,
                "importance_score": round(t.importance_score, 2),
                "course_outcomes": linked_cos,
                "status": st,
                "mastery_score": m.mastery_score if m else 0.0,
                "confidence_level": m.confidence_level if m else "none",
                "created_at": t.created_at.isoformat() if t.created_at else None,
            })

        units_data.append({
            "id": u.id,
            "unit_number": u.unit_number,
            "title": u.title,
            "description": u.description,
            "weightage_percent": u.weightage_percent,
            "topics": topics_data,
        })

    return {
        "course_id": course.id,
        "course_name": course.name,
        "total_units": len(units_data),
        "total_topics": total_topics,
        "units": units_data,
        "outcomes": [{"id": o.id, "co_code": o.co_code, "description": o.description, "target_level": o.target_level} for o in outcomes],
    }


@router.post("/units", status_code=status.HTTP_201_CREATED)
def add_unit(
    course_id: int,
    req: CreateUnitRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    unit = CourseUnit(
        course_id=course_id,
        unit_number=req.unit_number,
        title=req.title.strip(),
        description=req.description.strip(),
        weightage_percent=req.weightage_percent,
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return {"id": unit.id, "unit_number": unit.unit_number, "title": unit.title}


@router.post("/topics", status_code=status.HTTP_201_CREATED)
def add_topic(
    course_id: int,
    req: CreateTopicRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    unit = db.query(CourseUnit).filter(CourseUnit.id == req.unit_id, CourseUnit.course_id == course_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found in course")

    topic = SyllabusTopic(
        course_id=course_id,
        unit_id=req.unit_id,
        name=req.name.strip(),
        bloom_level=req.bloom_level.strip(),
        importance_score=req.importance_score,
    )
    db.add(topic)
    db.flush()

    for co_id in req.outcome_ids:
        link = TopicOutcomeLink(topic_id=topic.id, outcome_id=co_id)
        db.add(link)

    db.commit()
    db.refresh(topic)
    return {"id": topic.id, "name": topic.name, "bloom_level": topic.bloom_level}


@router.delete("/topics/{topic_id}")
def delete_topic(
    course_id: int,
    topic_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id, SyllabusTopic.course_id == course_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    db.delete(topic)
    db.commit()
    return {"status": "deleted", "id": str(topic_id)}


@router.post("/extract")
async def extract_syllabus(
    course_id: int,
    req: ExtractSyllabusRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """AI Syllabus Extraction using Ollama Qwen3.5:4b local LLM.

    Extracts units and topics from uploaded syllabus PDF segments or raw text.
    """
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    content = ""
    if req.source_id:
        source = db.query(Source).filter(Source.id == req.source_id, Source.user_id == user.id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Source document not found")
        segments = db.query(Segment).filter(Segment.source_id == req.source_id).order_by(Segment.index).all()
        content = "\n".join([s.text for s in segments if s.text])[:8000]
    elif req.raw_text:
        content = req.raw_text.strip()[:8000]
    else:
        raise HTTPException(status_code=400, detail="Either source_id or raw_text is required")

    prompt = f"""You are an expert academic curriculum parser.
Analyze the following university syllabus text and extract the academic units and their respective topics.
Assign each topic an appropriate Bloom's taxonomy cognitive level: ("Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create").

Return ONLY valid JSON matching this exact structure:
{{
  "units": [
    {{
      "unit_number": 1,
      "title": "Unit Title Here",
      "topics": [
        {{"name": "Topic name", "bloom_level": "Understand"}},
        {{"name": "Another topic", "bloom_level": "Apply"}}
      ]
    }}
  ]
}}

Syllabus Text:
{content}
"""
    try:
        response_text = await call_ollama_text(prompt, model="qwen3.5:4b", temperature=0.1)
        # Parse json from output
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start != -1 and json_end != -1:
            data = json.loads(response_text[json_start:json_end])
        else:
            raise ValueError("No JSON detected in LLM response")

        extracted_units = data.get("units", [])
        saved_units = []
        total_topics = 0

        for u_data in extracted_units:
            unit_num = int(u_data.get("unit_number", 1))
            unit_title = str(u_data.get("title", f"Unit {unit_num}"))[:255]

            # Find or create unit
            unit = db.query(CourseUnit).filter(
                CourseUnit.course_id == course_id,
                CourseUnit.unit_number == unit_num
            ).first()
            if not unit:
                unit = CourseUnit(
                    course_id=course_id,
                    unit_number=unit_num,
                    title=unit_title,
                    weightage_percent=round(100.0 / max(1, len(extracted_units)), 1),
                )
                db.add(unit)
                db.flush()

            for t_data in u_data.get("topics", []):
                t_name = str(t_data.get("name", "")).strip()[:255]
                bloom = str(t_data.get("bloom_level", "Understand"))[:32]
                if t_name:
                    topic = SyllabusTopic(
                        course_id=course_id,
                        unit_id=unit.id,
                        name=t_name,
                        bloom_level=bloom,
                        importance_score=1.0,
                    )
                    db.add(topic)
                    total_topics += 1

            saved_units.append({"unit_number": unit_num, "title": unit_title})

        db.commit()
        return {
            "status": "success",
            "units_extracted": len(saved_units),
            "topics_extracted": total_topics,
            "units": saved_units,
        }
    except Exception as exc:
        log.warning("AI syllabus extraction failed or degraded: %s", exc)
        # Fallback heuristic: create default 6 units for standard university engineering structure
        if not db.query(CourseUnit).filter(CourseUnit.course_id == course_id).count():
            for i in range(1, 7):
                u = CourseUnit(
                    course_id=course_id,
                    unit_number=i,
                    title=f"Unit {i}: Module Fundamentals",
                    weightage_percent=16.6,
                )
                db.add(u)
                db.flush()
                t = SyllabusTopic(course_id=course_id, unit_id=u.id, name=f"Core Concepts of Unit {i}", bloom_level="Understand")
                db.add(t)
            db.commit()
        return {"status": "fallback_applied", "message": f"Applied default curriculum units ({exc})"}
