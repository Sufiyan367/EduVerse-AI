from pathlib import Path

p = Path("S:/SY/SEM 3/MP/EduVerse_Web_Demo/backend/quicklearn/api/quiz.py")
content = p.read_text(encoding="utf-8")

old_start = "@router.post(\"/session/{session_id}/answer\")\nasync def submit_answer(session_id: int, payload: AnswerRequest) -> dict[str, Any]:"
old_end = "    return response\n\n\n@router.get(\"/session/{session_id}/results\")"

idx_start = content.find(old_start)
idx_end = content.find(old_end)

assert idx_start != -1, "Start not found"
assert idx_end != -1, "End not found"

replacement = """@router.post("/session/{session_id}/answer")
async def submit_answer(session_id: int, payload: AnswerRequest) -> dict[str, Any]:
    # 1. Scope, Session Status & Idempotency pre-check
    def precheck() -> tuple[QuizItem, bool, float]:
        with session_scope() as session:
            row = session.get(QuizSession, session_id)
            if row is None:
                raise NotFoundError(f"Quiz session {session_id} not found.")
            if row.status is not QuizSessionStatus.ACTIVE:
                raise ValidationError("This session has already finished.")

            item = session.get(QuizItem, payload.item_id)
            if item is None:
                raise NotFoundError(f"Question {payload.item_id} not found.")

            # Scope enforcement: item must belong to session sources
            if row.source_ids and item.source_id not in row.source_ids:
                raise ValidationError(f"Question {payload.item_id} is outside the scope of this quiz session.")

            concept = session.get(Concept, item.concept_id) if item.concept_id else None
            current_mastery = concept.mastery if concept else 0.0

            # Idempotency check: prevent duplicate submissions from inflating mastery
            existing = session.execute(
                select(QuizAttempt).where(
                    QuizAttempt.session_id == session_id,
                    QuizAttempt.quiz_item_id == payload.item_id,
                )
            ).scalar_one_or_none()

            if existing is not None:
                session.expunge(existing)
                session.expunge(item)
                return item, True, current_mastery

            session.expunge(item)
            return item, False, current_mastery

    item, is_duplicate, current_mastery = await run_db(precheck)

    if is_duplicate:
        # Return existing attempt without creating duplicate or applying mastery update again
        def fetch_existing() -> dict[str, Any]:
            with session_scope() as session:
                row = session.get(QuizSession, session_id)
                is_test = row is not None and row.mode is QuizMode.TEST
                att = session.execute(
                    select(QuizAttempt).where(
                        QuizAttempt.session_id == session_id,
                        QuizAttempt.quiz_item_id == payload.item_id,
                    )
                ).scalar_one()
                resp = {
                    "item_id": payload.item_id,
                    "score": round(att.score or 0.0, 3),
                    "mastery": current_mastery,
                    "duplicate": True,
                }
                if not is_test:
                    resp["is_correct"] = att.is_correct
                    resp["feedback"] = att.feedback
                    resp["correct_answer"] = item.answer
                    resp["explanation"] = item.explanation
                    resp["segment_ids"] = list(item.segment_ids or [])
                return resp
        return await run_db(fetch_existing)

    grade = await quiz_gen.grade_answer(item, payload.response)

    # 2. Defect 4 Fix: If grading failed due to provider outage, DO NOT penalize mastery!
    if not grade.is_graded:
        def persist_ungraded() -> dict[str, Any]:
            with session_scope() as session:
                session.add(
                    QuizAttempt(
                        session_id=session_id,
                        quiz_item_id=payload.item_id,
                        response=payload.response,
                        is_correct=False,
                        score=0.0,
                        feedback=grade.feedback,
                    )
                )
                return {
                    "item_id": payload.item_id,
                    "score": 0.0,
                    "mastery": current_mastery,  # Mastery remains unpenalized
                    "is_correct": False,
                    "is_graded": False,
                    "feedback": grade.feedback,
                    "error": grade.error,
                }
        return await run_db(persist_ungraded)

    # 3. Valid Grading: Persist attempt and update mastery in one atomic transaction
    def persist_valid() -> dict[str, Any]:
        with session_scope() as session:
            row = session.get(QuizSession, session_id)
            is_test = row is not None and row.mode is QuizMode.TEST
            session.add(
                QuizAttempt(
                    session_id=session_id,
                    quiz_item_id=payload.item_id,
                    response=payload.response,
                    is_correct=grade.is_correct,
                    score=grade.score,
                    feedback=grade.feedback,
                )
            )

            # Atomic mastery update
            new_mastery = current_mastery
            if item.concept_id is not None:
                concept = session.get(Concept, item.concept_id)
                if concept is not None:
                    if grade.is_correct:
                        concept.mastery = min(1.0, concept.mastery + (1.0 - concept.mastery) * 0.3)
                    else:
                        weight = grade.score if grade.score > 0.0 else 0.5
                        concept.mastery = max(0.0, concept.mastery * weight)
                    new_mastery = round(concept.mastery, 3)

            resp: dict[str, Any] = {
                "item_id": payload.item_id,
                "score": round(grade.score, 3),
                "mastery": new_mastery,
            }
            if not is_test:
                resp["is_correct"] = grade.is_correct
                resp["feedback"] = grade.feedback
                resp["correct_answer"] = item.answer
                resp["explanation"] = item.explanation
                resp["segment_ids"] = list(item.segment_ids or [])
            return resp

    return await run_db(persist_valid)
"""

new_content = content[:idx_start] + replacement + content[idx_end + len("    return response\n"):]
p.write_text(new_content, encoding="utf-8")
print("Successfully patched api/quiz.py submit_answer!")
