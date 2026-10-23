from pathlib import Path

path = Path("S:/SY/SEM 3/MP/EduVerse_Web_Demo/backend/quicklearn/api/quiz.py")
content = path.read_text(encoding="utf-8")

old = """        def persist_ungraded() -> dict[str, Any]:
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
        return await run_db(persist_ungraded)"""

new = """        def persist_ungraded() -> dict[str, Any]:
            with session_scope() as session:
                row = session.get(QuizSession, session_id)
                is_test = row is not None and row.mode is QuizMode.TEST
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
                resp: dict[str, Any] = {
                    "item_id": payload.item_id,
                    "score": 0.0,
                    "mastery": current_mastery,
                    "is_graded": False,
                    "error": grade.error,
                }
                if not is_test:
                    resp["is_correct"] = False
                    resp["feedback"] = grade.feedback
                return resp
        return await run_db(persist_ungraded)"""

if old in content:
    path.write_text(content.replace(old, new, 1), encoding="utf-8")
    print("Updated persist_ungraded successfully.")
else:
    print("old block not found in quiz.py")
