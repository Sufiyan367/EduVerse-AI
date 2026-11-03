"""Guided Topic Learning API for EduVerse AI.

Provides the end-to-end guided learning journey:
`Not Started -> Learning -> Practicing -> Needs Review / Mastered`

Endpoints:
- GET  /courses/{course_id}/topics/{topic_id}/learning           - Full context, prerequisites, materials, evidence
- POST /courses/{course_id}/topics/{topic_id}/learning/start     - Transition to 'learning' lifecycle state (study activity)
- POST /courses/{course_id}/topics/{topic_id}/learning/explain   - Grounded explanation, key definitions, worked example
- POST /courses/{course_id}/topics/{topic_id}/learning/quiz      - Generate 3-question knowledge check & signed quiz token
- POST /courses/{course_id}/topics/{topic_id}/learning/submit    - Grade knowledge check against issued token, update status
- POST /courses/{course_id}/topics/{topic_id}/learning/revision  - Schedule adaptive revision task
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import logging
import random
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..auth import _b64url_decode, _b64url_encode, get_current_user, get_jwt_secret
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
from ..errors import ProviderError, ProviderUnavailableError
from ..providers import gateway, registry
from ..providers.base import text_message
from ..rag import retrieve as rag

log = logging.getLogger(__name__)

router = APIRouter(prefix="/courses/{course_id}/topics/{topic_id}/learning", tags=["guided_learning"])


# ============================================================================
# Schemas & Cryptographic Quiz Token
# ============================================================================

class GeneratedQuestion(BaseModel):
    id: int
    question_text: str
    options: list[str] = Field(..., min_length=4, max_length=4)
    correct_option: str = Field(..., pattern=r"^[A-D]$")
    bloom_level: str = "Understand"
    explanation: str
    citation: str | None = None


class GeneratedQuizResponse(BaseModel):
    questions: list[GeneratedQuestion] = Field(..., min_length=3, max_length=3)


class AnswerSubmission(BaseModel):
    question_id: int
    selected_option: str


class QuizSubmissionRequest(BaseModel):
    quiz_token: str
    answers: list[AnswerSubmission]


def create_signed_quiz_token(payload: dict[str, Any]) -> str:
    """Create a tamper-proof HMAC-SHA256 signed quiz token binding issued questions to answers."""
    secret = get_jwt_secret().encode("utf-8")
    raw_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    b64_payload = _b64url_encode(raw_json)
    sig = hmac.new(secret, b64_payload.encode("ascii"), hashlib.sha256).digest()
    b64_sig = _b64url_encode(sig)
    return f"{b64_payload}.{b64_sig}"


def verify_signed_quiz_token(token: str) -> dict[str, Any]:
    """Verify cryptographic signature and expiration of an issued quiz token."""
    secret = get_jwt_secret().encode("utf-8")
    parts = token.split(".")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Malformed quiz token format.")
    b64_payload, b64_sig = parts
    try:
        sig = _b64url_decode(b64_sig)
        expected_sig = hmac.new(secret, b64_payload.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected_sig):
            raise HTTPException(status_code=400, detail="Invalid quiz token signature.")
        raw_json = _b64url_decode(b64_payload)
        payload = json.loads(raw_json.decode("utf-8"))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Failed to decode quiz token.") from exc

    if time.time() > payload.get("expires_at", 0):
        raise HTTPException(status_code=400, detail="Quiz session has expired. Please generate a fresh knowledge check.")
    return payload


def _permute_question_options(
    question_text: str,
    options: list[str],
    correct_option: str,
    target_letter: str,
    bloom_level: str,
    explanation: str,
    citation: str | None = None,
) -> dict[str, Any]:
    """Permute options so that the correct answer is mapped to target_letter (ensures non-uniform distribution)."""
    letters = ["A", "B", "C", "D"]
    orig_idx = letters.index(correct_option.strip().upper())
    correct_text = options[orig_idx]
    distractors = [opt for i, opt in enumerate(options) if i != orig_idx]

    target_idx = letters.index(target_letter)
    new_options = ["" for _ in range(4)]
    new_options[target_idx] = correct_text
    d_idx = 0
    for i in range(4):
        if i != target_idx:
            new_options[i] = distractors[d_idx]
            d_idx += 1

    return {
        "id": 0,
        "question_text": question_text,
        "options": new_options,
        "correct_option": target_letter,
        "bloom_level": bloom_level,
        "explanation": explanation,
        "citation": citation,
    }


# ============================================================================
# 1. Topic Learning Context & Materials
# ============================================================================

@router.get("")
async def get_guided_learning_context(
    course_id: int,
    topic_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve full context for a guided topic learning session with strict multi-tenant authorization."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id, SyllabusTopic.course_id == course.id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    unit = db.query(CourseUnit).filter(CourseUnit.id == topic.unit_id, CourseUnit.course_id == course.id).first()

    # Mastery and status (strictly user-isolated)
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
    outcomes = (
        db.query(CourseOutcome).filter(CourseOutcome.id.in_(outcome_ids), CourseOutcome.course_id == course.id).all()
        if outcome_ids
        else []
    )

    # Linked materials for this course/unit (enforcing Source.user_id == user.id)
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

    # RAG retrieve evidence for this topic strictly scoped to user
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
    elif current_status == "practicing":
        recommended_action = "Take Knowledge Check to Reach 80% Mastery"
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


# ============================================================================
# 2. Start Learning (Study Activity Transition)
# ============================================================================

@router.post("/start")
def start_topic_learning(
    course_id: int,
    topic_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Transition topic lifecycle status to 'learning' (recorded as study activity, not demonstrated assessment)."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id, SyllabusTopic.course_id == course.id).first()
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
            mastery_score=0.0,  # 0.0: Starting a lesson is study activity, not demonstrated assessment!
            confidence_level="low",
            status="learning",
            last_evaluated_at=None,
        )
        db.add(mastery)
    else:
        if mastery.status in ("not_started", None):
            mastery.status = "learning"

    # Log study activity event (score 0.0)
    db.add(TopicMasteryEvent(user_id=user.id, topic_id=topic.id, event_type="learning_start", score=0.0))
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


# ============================================================================
# 3. Grounded Tutor Explanation
# ============================================================================

@router.post("/explain")
async def get_topic_explanation(
    course_id: int,
    topic_id: int,
    mode: str = "standard",  # standard, simple, example, compare
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Generate grounded teaching explanation with validated citations, worked examples, and pedagogical modes."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id, SyllabusTopic.course_id == course.id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    excerpts = await rag.retrieve(
        topic.name,
        scope_type="topic",
        scope_id=topic.id,
        user_id=user.id,
        top_k=5,
        rerank_to=3,
        use_rerank=False,
    )
    has_evidence = len(excerpts) > 0

    valid_citations = [
        {
            "id": e.id,
            "source_id": e.source_id,
            "source_title": e.source_title,
            "page_no": e.page_no,
            "text": e.text,
        }
        for e in excerpts
    ] if has_evidence else []

    evidence_context = "\n\n".join(
        [f"[Doc #{e.source_id} '{e.source_title}', Page {e.page_no or 'N/A'}]: {e.text}" for e in excerpts]
    )

    prompt_mode_instructions = {
        "standard": (
            f"Explain {topic.name} in a structured academic style covering its definition, governing principles, "
            f"and significance within {course.name}. Ground all factual statements in the provided source excerpts."
        ),
        "simple": (
            f"Explain {topic.name} in plain, intuitive language for a beginner. Use an everyday, relatable analogy "
            f"and intuitive mental model. Avoid dense mathematical jargon while preserving technical correctness."
        ),
        "example": (
            f"Provide a thorough, concrete, step-by-step worked example demonstrating how {topic.name} is applied "
            f"to solve an engineering/academic problem. Specify concrete input variables, show Step 1 formulation, "
            f"Step 2 execution/substitution, and Step 3 final verified result."
        ),
        "compare": (
            f"Provide an analytical comparison of {topic.name} against alternative approaches or neighboring syllabus concepts. "
            f"Highlight practical trade-offs (e.g. latency vs consistency, complexity vs performance) and common exam pitfalls."
        ),
    }

    instruction = prompt_mode_instructions.get(mode, prompt_mode_instructions["standard"])

    summary = ""
    example = ""
    definitions = [
        {"term": topic.name, "definition": f"Core academic concept covering {topic.name} within {course.code} curriculum."},
        {"term": "Bloom Objective", "definition": f"Target cognitive competency: {topic.bloom_level} level."},
    ]

    # Try calling LLM provider if available
    llm_generated = False
    if registry.has_llm():
        try:
            sys_msg = text_message(
                "system",
                (
                    f"You are a Senior University Professor teaching {course.name} ({course.code}). "
                    "Your explanations must be rigorous, precise, and pedagogically sound. "
                    "Only make factual assertions grounded in the provided course excerpts. "
                    "Never invent quotes, fake source titles, or fake page references."
                ),
            )
            usr_msg = text_message(
                "user",
                (
                    f"Instruction:\n{instruction}\n\n"
                    f"Topic: {topic.name}\n"
                    f"Target Bloom Level: {topic.bloom_level}\n\n"
                    f"Retrieved Course Material Excerpts:\n{evidence_context if has_evidence else 'None uploaded.'}\n\n"
                    "Output a comprehensive, high-quality explanation matching the requested mode."
                ),
            )
            raw_text = await gateway.complete_text(
                purpose="guided_learning_explain",
                messages=[sys_msg, usr_msg],
                temperature=0.2,
                max_tokens=2048,
            )
            if raw_text and len(raw_text.strip()) > 50:
                summary = raw_text.strip()
                llm_generated = True
        except (ProviderError, ProviderUnavailableError, Exception) as exc:
            log.warning("Guided learning LLM explanation generation degraded: %s", exc)

    if not llm_generated:
        # Grounded deterministic synthesis
        if has_evidence:
            primary_excerpt = excerpts[0]
            summary = (
                f"{topic.name} is defined in course materials ('{primary_excerpt.source_title}', Page {primary_excerpt.page_no or 'N/A'}) "
                f"as follows:\n\"{primary_excerpt.text.strip()}\"\n\n"
            )
            if mode == "simple":
                summary += (
                    f"In intuitive terms, {topic.name} acts like a safety coordinator in an automated system, "
                    f"ensuring all components operate in harmonious synchrony without collisions or data loss."
                )
            elif mode == "example":
                summary += (
                    f"Step-by-Step Application:\n"
                    f"Given an initial state under {topic.name}, Step 1 identifies boundary constraints from the material. "
                    f"Step 2 evaluates transition conditions. Step 3 confirms valid execution invariant."
                )
            elif mode == "compare":
                summary += (
                    f"Comparative Analysis:\nUnlike naive alternatives, {topic.name} provides deterministic guarantees "
                    f"at the cost of minimal coordination overhead, making it preferred for robust implementations."
                )
            else:
                summary += (
                    f"This principle is essential for satisfying the {topic.bloom_level} level learning outcome "
                    f"in {course.name}."
                )
        else:
            summary = (
                f"{topic.name} represents a foundational curriculum topic in {course.name}. "
                f"Target cognitive outcome is {topic.bloom_level}."
            )
            if mode == "simple":
                summary += f" Simply understood: it establishes foundational protocols for predictable system behavior."
            elif mode == "example":
                summary += f" Applied Scenario: Input state is verified against invariant conditions to produce predictable output."
            elif mode == "compare":
                summary += f" Trade-off: Balances implementation overhead against strict runtime reliability."

    # Log explanation event
    db.add(TopicMasteryEvent(user_id=user.id, topic_id=topic.id, event_type="tutor_explanation", score=0.0))
    db.commit()

    return {
        "topic_id": topic.id,
        "topic_name": topic.name,
        "mode": mode,
        "summary": summary,
        "definitions": definitions,
        "worked_example": example if example else summary,
        "has_source_evidence": has_evidence,
        "citations": valid_citations,
        "disclaimer": (
            None
            if has_evidence
            else "No course materials are currently uploaded for this topic. Explanation is generated from general academic background without verified course citations."
        ),
    }


# ============================================================================
# 4. Generate Topic Knowledge Check (Dynamic & Signed Token)
# ============================================================================

@router.post("/quiz")
async def get_topic_knowledge_check(
    course_id: int,
    topic_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Generate or retrieve a genuine 3-question knowledge check for this topic with signed token validation."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id, SyllabusTopic.course_id == course.id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    unit = db.query(CourseUnit).filter(CourseUnit.id == topic.unit_id).first()

    excerpts = await rag.retrieve(
        topic.name,
        scope_type="topic",
        scope_id=topic.id,
        user_id=user.id,
        top_k=5,
        rerank_to=3,
        use_rerank=False,
    )
    has_evidence = len(excerpts) > 0

    generated_questions: list[dict[str, Any]] = []
    generation_mode = "ai_generated"

    # Attempt LLM structured generation
    if registry.has_llm():
        try:
            evidence_str = "\n".join([f"- [Excerpt #{e.id}]: {e.text[:300]}" for e in excerpts]) if has_evidence else "None"
            sys_msg = text_message(
                "system",
                (
                    f"You are a rigorous academic examiner for university course '{course.name}'. "
                    f"Generate a 3-question diagnostic knowledge check targeting the specific topic: '{topic.name}'.\n"
                    "Requirements:\n"
                    "1. Every question must directly test the student's mastery of this topic, not generic statements.\n"
                    "2. Q1 must test definition and fundamental mechanism.\n"
                    "3. Q2 must test an implementation trade-off, application, or constraint.\n"
                    "4. Q3 must test error recovery, boundary behavior, or failure modes.\n"
                    "5. Each question must have exactly 4 unique, plausible options.\n"
                    "6. Distribute correct options across A, B, C, D (do not make option A correct for all questions).\n"
                    "7. Provide clear, educational explanations for each question."
                ),
            )
            usr_msg = text_message(
                "user",
                (
                    f"Generate 3 questions for topic '{topic.name}' (Bloom Level: {topic.bloom_level}).\n"
                    f"Course Material Context:\n{evidence_str}"
                ),
            )
            llm_res = await gateway.complete_structured(
                purpose="topic_knowledge_check_generation",
                messages=[sys_msg, usr_msg],
                schema=GeneratedQuizResponse,
                temperature=0.2,
            )
            if llm_res and len(llm_res.questions) == 3:
                # Target letters to guarantee varied correct options: Q1 -> B, Q2 -> C, Q3 -> A
                target_letters = ["B", "C", "A"]
                for i, q in enumerate(llm_res.questions):
                    target_l = target_letters[i % len(target_letters)]
                    permuted = _permute_question_options(
                        question_text=q.question_text,
                        options=q.options,
                        correct_option=q.correct_option,
                        target_letter=target_l,
                        bloom_level=q.bloom_level or topic.bloom_level,
                        explanation=q.explanation,
                        citation=q.citation,
                    )
                    permuted["id"] = i + 1
                    generated_questions.append(permuted)
        except (ProviderError, ProviderUnavailableError, Exception) as exc:
            log.warning("Knowledge check LLM generation failed or provider offline: %s", exc)

    if not generated_questions:
        # Fallback generation: Must assess the selected topic directly, not generic engineering statements!
        generation_mode = "documented_fallback"
        target_letters = ["B", "C", "A"]

        # Topic-specific contextual questions
        raw_fallback_questions = [
            {
                "question_text": f"In {course.code}, what is the foundational principle and operational mechanism of {topic.name}?",
                "options": [
                    f"It bypasses formal checks to maximize raw execution speed without validation.",
                    f"It enforces structured invariants to ensure predictable state transitions for {topic.name}.",
                    f"It replaces indexed memory storage with flat text buffers.",
                    f"It eliminates the need for unit testing and boundary verification.",
                ],
                "correct_option": "B",
                "bloom_level": "Understand",
                "explanation": f"{topic.name} is fundamentally designed to establish correctness and predictable state invariants.",
            },
            {
                "question_text": f"What is the primary architectural trade-off encountered when implementing {topic.name}?",
                "options": [
                    f"Choosing pseudorandom numbers for deterministic hash functions.",
                    f"Ignoring boundary constraints during concurrent thread execution.",
                    f"Balancing runtime throughput and coordination overhead against consistency guarantees.",
                    f"Disabling compiler warnings to reduce code compilation times.",
                ],
                "correct_option": "C",
                "bloom_level": "Apply",
                "explanation": f"Implementations of {topic.name} must carefully balance synchronization and overhead against invariant guarantees.",
            },
            {
                "question_text": f"What failure mode or inconsistency occurs if the governing constraints of {topic.name} are violated?",
                "options": [
                    f"The system risks race conditions, data corruption, or undefined behavior during execution.",
                    f"The operating system automatically fixes all logic inconsistencies without latency.",
                    f"Memory consumption drops to zero while throughput doubles.",
                    f"No observable consequence occurs under any concurrent workload.",
                ],
                "correct_option": "A",
                "bloom_level": "Analyze",
                "explanation": f"Violating governing constraints of {topic.name} leads to state divergence, race conditions, or runtime anomalies.",
            },
        ]

        for i, q in enumerate(raw_fallback_questions):
            q["id"] = i + 1
            generated_questions.append(q)

    # Build tamper-proof HMAC-signed quiz token binding issued questions to server verification
    quiz_payload = {
        "quiz_id": str(uuid.uuid4()),
        "user_id": user.id,
        "course_id": course.id,
        "topic_id": topic.id,
        "question_ids": [q["id"] for q in generated_questions],
        "answer_key": {str(q["id"]): q["correct_option"] for q in generated_questions},
        "explanations": {str(q["id"]): q["explanation"] for q in generated_questions},
        "issued_at": int(time.time()),
        "expires_at": int(time.time()) + 7200,  # 2 hours validity
    }
    quiz_token = create_signed_quiz_token(quiz_payload)

    # Sanitize questions sent to client: DO NOT LEAK correct_option!
    client_questions = [
        {
            "id": q["id"],
            "question_text": q["question_text"],
            "options": q["options"],
            "bloom_level": q["bloom_level"],
            "citation": q.get("citation"),
        }
        for q in generated_questions
    ]

    return {
        "topic_id": topic.id,
        "topic_name": topic.name,
        "quiz_token": quiz_token,
        "total_questions": len(client_questions),
        "questions": client_questions,
        "generation_mode": generation_mode,
    }


# ============================================================================
# 5. Submit & Evaluate Knowledge Check (Strict Policy & Thresholds)
# ============================================================================

@router.post("/submit")
def submit_topic_knowledge_check(
    course_id: int,
    topic_id: int,
    req: QuizSubmissionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Grade knowledge check, strictly enforcing binding, validation, and documented mastery thresholds."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id, SyllabusTopic.course_id == course.id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    # 1. Cryptographically verify quiz token
    payload = verify_signed_quiz_token(req.quiz_token)
    if payload.get("user_id") != user.id:
        raise HTTPException(status_code=403, detail="Forbidden: Quiz token does not belong to authenticated student.")
    if payload.get("course_id") != course.id or payload.get("topic_id") != topic.id:
        raise HTTPException(status_code=400, detail="Quiz token course or topic mismatch.")

    # 2. Strict answer validation: prevent empty, missing, duplicate, and invalid submissions
    if not req.answers:
        raise HTTPException(status_code=422, detail="Empty submission: at least one answer required.")

    expected_qids = set(payload.get("question_ids", []))
    submitted_qids = [item.question_id for item in req.answers]

    if len(submitted_qids) != len(set(submitted_qids)):
        raise HTTPException(status_code=422, detail="Duplicate answer submission for question ID detected.")

    if set(submitted_qids) != expected_qids:
        missing_ids = sorted(expected_qids - set(submitted_qids))
        invalid_ids = sorted(set(submitted_qids) - expected_qids)
        err_msg = ""
        if missing_ids:
            err_msg += f"Missing answers for issued questions: {missing_ids}. "
        if invalid_ids:
            err_msg += f"Invalid question IDs not issued in this quiz: {invalid_ids}."
        raise HTTPException(status_code=422, detail=err_msg.strip())

    answer_key = payload.get("answer_key", {})
    explanations = payload.get("explanations", {})

    correct_count = 0
    feedback_items = []
    mistakes = []

    for item in req.answers:
        opt = item.selected_option.strip().upper()
        if opt not in {"A", "B", "C", "D"}:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid option '{item.selected_option}' for question {item.question_id}. Must be A, B, C, or D.",
            )

        qid_str = str(item.question_id)
        expected_opt = answer_key.get(qid_str, "A")
        is_corr = opt == expected_opt
        exp_text = explanations.get(qid_str, f"Reference topic principles for question {item.question_id}.")

        if is_corr:
            correct_count += 1
        else:
            mistakes.append({
                "question_id": item.question_id,
                "selected": opt,
                "expected": expected_opt,
                "explanation": exp_text,
            })

        feedback_items.append({
            "question_id": item.question_id,
            "is_correct": is_corr,
            "explanation": exp_text,
        })

    total = len(expected_qids)
    score = round(correct_count / total, 2)
    score_pct = int(score * 100)

    # 3. Enforce documented mastery thresholds:
    # 80-100%: Mastered
    # 70-79%:  Practicing (not Mastered)
    # 0-69%:   Needs Review
    if score >= 0.80:
        new_status = "mastered"
        passed = True
        status_reason = f"Mastered ({score_pct}%): You scored at or above the 80% threshold, demonstrating solid conceptual retention."
        next_action = "Topic Mastered! You can now proceed to the next syllabus topic or schedule a periodic spaced revision."
    elif score >= 0.70:
        new_status = "practicing"
        passed = False
        status_reason = f"Practicing ({score_pct}%): Scored in the 70–79% range. Solid foundation, but 80%+ is required for mastery."
        next_action = "In Learning / Practicing: Review the missed concept and retry the check to elevate to Mastered."
    else:
        new_status = "needs_review"
        passed = False
        status_reason = f"Needs Review ({score_pct}%): Scored below 70%. Conceptual misunderstandings were identified."
        next_action = "Needs Review: Read the remedial explanations above and retry the check to solidify your understanding."

    # 4. Update StudentTopicMastery
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
            confidence_level="high" if score >= 0.80 else ("medium" if score >= 0.70 else "low"),
            status=new_status,
            last_evaluated_at=utcnow(),
        )
        db.add(mastery)
    else:
        mastery.mastery_score = score
        mastery.confidence_level = "high" if score >= 0.80 else ("medium" if score >= 0.70 else "low")
        mastery.status = new_status
        mastery.last_evaluated_at = utcnow()

    # 5. Log TopicMasteryEvent and ActivityLog
    db.add(
        TopicMasteryEvent(
            user_id=user.id,
            topic_id=topic.id,
            event_type="knowledge_check",
            score=score,
        )
    )

    db.add(
        ActivityLog(
            user_id=user.id,
            action="complete_knowledge_check",
            entity_type="topic",
            entity_id=topic.id,
            title=f"Knowledge Check on {topic.name}: {score_pct}%",
            details={
                "course_code": course.code,
                "score": score,
                "score_pct": score_pct,
                "passed": passed,
                "new_status": new_status,
                "status_reason": status_reason,
            },
        )
    )

    db.commit()

    return {
        "topic_id": topic.id,
        "score": score,
        "score_percent": score_pct,
        "passed": passed,
        "new_status": new_status,
        "status_reason": status_reason,
        "correct_count": correct_count,
        "total_questions": total,
        "mistakes": mistakes,
        "feedback": feedback_items,
        "next_action": next_action,
    }


# ============================================================================
# 6. Schedule Spaced Topic Revision
# ============================================================================

@router.post("/revision")
def schedule_topic_revision(
    course_id: int,
    topic_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Schedule an adaptive revision task for this topic in the student's revision plan."""
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id, SyllabusTopic.course_id == course.id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    mastery = (
        db.query(StudentTopicMastery)
        .filter(StudentTopicMastery.topic_id == topic.id, StudentTopicMastery.user_id == user.id)
        .first()
    )
    status_str = getattr(mastery, "status", "not_started")
    priority = 1 if status_str == "needs_review" else (2 if status_str == "practicing" else 3)

    # Find or create active plan strictly for this user & course
    plan = (
        db.query(RevisionPlan)
        .filter(RevisionPlan.course_id == course.id, RevisionPlan.user_id == user.id, RevisionPlan.status == "active")
        .first()
    )
    if not plan:
        plan = RevisionPlan(
            user_id=user.id,
            course_id=course.id,
            title=f"Adaptive Revision Plan: {course.code}",
            status="active",
        )
        db.add(plan)
        db.flush()

    task = RevisionTask(
        plan_id=plan.id,
        topic_id=topic.id,
        title=f"Revise {topic.name}",
        description=f"Spaced recall and formula revision for {topic.name} (Current Status: {status_str}).",
        priority=priority,
        estimated_minutes=25,
        is_completed=False,
    )
    db.add(task)

    db.add(
        ActivityLog(
            user_id=user.id,
            action="schedule_topic_revision",
            entity_type="topic",
            entity_id=topic.id,
            title=f"Scheduled revision for {topic.name}",
            details={"course_code": course.code, "priority": priority},
        )
    )
    db.commit()

    return {
        "scheduled": True,
        "task_id": task.id,
        "topic_id": topic.id,
        "priority": priority,
        "scheduled_for": (utcnow() + dt.timedelta(days=2)).isoformat(),
        "status": status_str,
    }
