"""Course Workspace API endpoints for EduVerse AI."""

from __future__ import annotations

import datetime as dt
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
    PreviousPaper,
    SyllabusTopic,
)
from ..db.models import Source, User
from ..db.session import get_db

router = APIRouter(prefix="/courses", tags=["courses"])


class CreateCourseRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=2, max_length=255)
    semester: str = Field(default="Semester 3", max_length=32)
    academic_year: str = Field(default="2025-2026", max_length=32)
    description: str = Field(default="")
    target_exam_date: dt.datetime | None = None


class UpdateCourseRequest(BaseModel):
    code: str | None = None
    name: str | None = None
    semester: str | None = None
    academic_year: str | None = None
    description: str | None = None
    target_exam_date: dt.datetime | None = None


class LinkMaterialRequest(BaseModel):
    source_id: int
    unit_id: int | None = None


@router.get("")
def list_courses(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List all courses belonging to the current user with unit, topic, and paper counts."""
    courses = db.query(Course).filter(Course.user_id == user.id).order_by(Course.created_at.desc()).all()

    result = []
    for c in courses:
        unit_count = db.query(func.count(CourseUnit.id)).filter(CourseUnit.course_id == c.id).scalar() or 0
        topic_count = db.query(func.count(SyllabusTopic.id)).filter(SyllabusTopic.course_id == c.id).scalar() or 0
        paper_count = db.query(func.count(PreviousPaper.id)).filter(PreviousPaper.course_id == c.id).scalar() or 0
        material_count = db.query(func.count(CourseMaterialLink.id)).filter(CourseMaterialLink.course_id == c.id).scalar() or 0

        result.append({
            "id": c.id,
            "code": c.code,
            "name": c.name,
            "semester": c.semester,
            "academic_year": c.academic_year,
            "description": c.description,
            "target_exam_date": c.target_exam_date.isoformat() if c.target_exam_date else None,
            "unit_count": unit_count,
            "topic_count": topic_count,
            "paper_count": paper_count,
            "material_count": material_count,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
def create_course(
    req: CreateCourseRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a new course workspace."""
    course = Course(
        user_id=user.id,
        code=req.code.strip(),
        name=req.name.strip(),
        semester=req.semester.strip(),
        academic_year=req.academic_year.strip(),
        description=req.description.strip(),
        target_exam_date=req.target_exam_date,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return {
        "id": course.id,
        "code": course.code,
        "name": course.name,
        "semester": course.semester,
        "academic_year": course.academic_year,
        "description": course.description,
        "target_exam_date": course.target_exam_date.isoformat() if course.target_exam_date else None,
        "created_at": course.created_at.isoformat() if course.created_at else None,
    }


@router.get("/{course_id}")
def get_course_detail(
    course_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve full course details including units, outcomes, and linked materials."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    units = db.query(CourseUnit).filter(CourseUnit.course_id == course.id).order_by(CourseUnit.unit_number).all()
    outcomes = db.query(CourseOutcome).filter(CourseOutcome.course_id == course.id).order_by(CourseOutcome.co_code).all()
    materials = (
        db.query(CourseMaterialLink, Source)
        .join(Source, CourseMaterialLink.source_id == Source.id)
        .filter(CourseMaterialLink.course_id == course.id)
        .all()
    )

    return {
        "id": course.id,
        "code": course.code,
        "name": course.name,
        "semester": course.semester,
        "academic_year": course.academic_year,
        "description": course.description,
        "target_exam_date": course.target_exam_date.isoformat() if course.target_exam_date else None,
        "created_at": course.created_at.isoformat() if course.created_at else None,
        "units": [
            {
                "id": u.id,
                "unit_number": u.unit_number,
                "title": u.title,
                "description": u.description,
                "weightage_percent": u.weightage_percent,
                "topic_count": len(u.topics),
            }
            for u in units
        ],
        "outcomes": [
            {
                "id": o.id,
                "co_code": o.co_code,
                "description": o.description,
                "target_level": o.target_level,
            }
            for o in outcomes
        ],
        "materials": [
            {
                "link_id": m[0].id,
                "source_id": m[1].id,
                "title": m[1].title,
                "kind": str(m[1].kind),
                "page_count": m[1].page_count,
                "unit_id": m[0].unit_id,
            }
            for m in materials
        ],
    }


@router.put("/{course_id}")
def update_course(
    course_id: int,
    req: UpdateCourseRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if req.code is not None:
        course.code = req.code.strip()
    if req.name is not None:
        course.name = req.name.strip()
    if req.semester is not None:
        course.semester = req.semester.strip()
    if req.academic_year is not None:
        course.academic_year = req.academic_year.strip()
    if req.description is not None:
        course.description = req.description.strip()
    if req.target_exam_date is not None:
        course.target_exam_date = req.target_exam_date

    db.commit()
    return {"status": "updated", "id": course.id}


@router.delete("/{course_id}")
def delete_course(
    course_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    db.delete(course)
    db.commit()
    return {"status": "deleted", "id": str(course_id)}


@router.post("/{course_id}/materials")
def link_material(
    course_id: int,
    req: LinkMaterialRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    source = db.query(Source).filter(Source.id == req.source_id, Source.user_id == user.id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    link = db.query(CourseMaterialLink).filter(
        CourseMaterialLink.course_id == course_id,
        CourseMaterialLink.source_id == req.source_id,
    ).first()
    if not link:
        link = CourseMaterialLink(
            course_id=course_id,
            source_id=req.source_id,
            unit_id=req.unit_id,
        )
        db.add(link)
    else:
        link.unit_id = req.unit_id
    db.commit()
    return {"status": "linked", "source_id": req.source_id, "course_id": course_id}
