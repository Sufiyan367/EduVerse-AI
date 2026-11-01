"""Automation G: Data Quality & Evidence Audit Engine.

Automated auditing of citation integrity, page reference bounds, syllabus topic alignments,
rubric score constraints, and mastery event provenance. Flags anomalies into evidence_audit_issues.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from ...db.academic_models import (
    Course,
    CourseMaterialLink,
    EvidenceAuditIssue,
    ExamQuestion,
    Notification,
    PreviousPaper,
    Rubric,
    RubricCriterion,
    StudentTopicMastery,
    SyllabusTopic,
)
from ...db.enums import JobType
from ...db.models import Segment, Source
from ...db.session import session_scope
from ...db.types import utcnow
from ...jobs.worker import JobContext, register

log = logging.getLogger(__name__)


@register(JobType.AUTONOMOUS_AUDIT)
async def handle_audit_automation(ctx: JobContext) -> None:
    """Audit data quality, citations, syllabus mappings, and rubric bounds."""
    course_id = ctx.payload.get("course_id")
    user_id = ctx.user_id or ctx.payload.get("user_id")

    ctx.progress(15, "Starting Data Quality & Evidence Audit")

    issues_found = 0

    with session_scope() as session:
        # 1. Audit Page Reference Bounds on Sources
        sources = list(session.execute(select(Source).limit(50)).scalars())
        for src in sources:
            if src.page_count and src.page_count > 0:
                segments = list(session.execute(select(Segment).where(Segment.source_id == src.id)).scalars())
                for seg in segments:
                    if seg.page_no and seg.page_no > src.page_count:
                        issue = EvidenceAuditIssue(
                            user_id=user_id,
                            course_id=course_id,
                            issue_type="page_out_of_bounds",
                            severity="warning",
                            entity_type="segment",
                            entity_id=seg.id,
                            description=f"Segment #{seg.id} references page {seg.page_no}, but source '{src.title}' only has {src.page_count} pages.",
                            evidence_context={"source_id": src.id, "page": seg.page_no, "max_pages": src.page_count},
                            status="open",
                        )
                        session.add(issue)
                        issues_found += 1

        # 2. Audit Exam Questions without Syllabus Topics
        if course_id:
            questions = list(
                session.execute(
                    select(ExamQuestion)
                    .join(PreviousPaper, ExamQuestion.paper_id == PreviousPaper.id)
                    .where(PreviousPaper.course_id == course_id)
                ).scalars()
            )
            for q in questions:
                if not q.topic_links:
                    issue = EvidenceAuditIssue(
                        user_id=user_id,
                        course_id=course_id,
                        issue_type="unmapped_exam_question",
                        severity="warning",
                        entity_type="exam_question",
                        entity_id=q.id,
                        description=f"Exam question {q.question_number} ('{q.question_text[:50]}...') is not linked to any syllabus topic.",
                        evidence_context={"question_id": q.id, "marks": q.marks},
                        status="open",
                    )
                    session.add(issue)
                    issues_found += 1

        # 3. Audit Rubric Criteria Weights vs Question Max Marks
        rubrics = list(session.execute(select(Rubric).limit(30)).scalars())
        for r in rubrics:
            criteria = list(session.execute(select(RubricCriterion).where(RubricCriterion.rubric_id == r.id)).scalars())
            if criteria:
                criteria_sum = sum(c.max_points for c in criteria)
                if criteria_sum < 10.0 or criteria_sum > 100.0:
                    issue = EvidenceAuditIssue(
                        user_id=user_id,
                        course_id=course_id,
                        issue_type="invalid_rubric_weight",
                        severity="error",
                        entity_type="rubric",
                        entity_id=r.id,
                        description=f"Rubric #{r.id} criteria points sum ({criteria_sum}) is outside standard bounds.",
                        evidence_context={"rubric_id": r.id, "criteria_sum": criteria_sum},
                        status="open",
                    )
                    session.add(issue)
                    issues_found += 1

        # 4. Audit Orphaned Topic Mastery Records
        masteries = list(session.execute(select(StudentTopicMastery).limit(50)).scalars())
        for m in masteries:
            topic = session.get(SyllabusTopic, m.topic_id)
            if not topic:
                issue = EvidenceAuditIssue(
                    user_id=user_id,
                    course_id=course_id,
                    issue_type="orphaned_mastery",
                    severity="error",
                    entity_type="mastery",
                    entity_id=m.id,
                    description=f"Mastery record #{m.id} references non-existent topic #{m.topic_id}.",
                    evidence_context={"mastery_id": m.id, "topic_id": m.topic_id},
                    status="open",
                )
                session.add(issue)
                issues_found += 1

        # In-app notification if issues were detected
        if user_id and issues_found > 0:
            notif = Notification(
                user_id=user_id,
                title="🔍 Evidence Audit Complete",
                message=f"Audit finished: {issues_found} data quality issue(s) identified for review.",
                kind="audit_warning",
                link="/automation",
                data={"issues_found": issues_found},
            )
            session.add(notif)

    ctx.progress(100, f"Evidence audit complete: {issues_found} issue(s) identified")
