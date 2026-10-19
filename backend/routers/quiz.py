from fastapi import APIRouter, HTTPException
from backend.schemas import (
    QuizGenerateRequest,
    QuizGenerateResponse,
    QuizEvaluateRequest,
    QuizEvaluationResponse,
    QuestionResult,
    QuizQuestion
)
from backend.services.storage_service import storage
from backend.services.llm_service import llm_service
from typing import List

router = APIRouter(prefix="/api/quiz", tags=["Quiz"])

@router.post("/generate", response_model=QuizGenerateResponse)
async def generate_quiz(req: QuizGenerateRequest):
    """
    Synthesizes Multiple-Choice Questions (MCQs) directly from the uploaded study material.
    """
    doc = storage.get_document(req.doc_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Study document '{req.doc_id}' not found. Please upload a PDF first."
        )

    try:
        raw_questions = llm_service.generate_quiz(
            document_context=doc["raw_text"],
            count=req.count
        )
        quiz_id = storage.store_quiz(doc_id=req.doc_id, questions=raw_questions)

        formatted_questions = [
            QuizQuestion(
                question_id=q["question_id"],
                question_text=q["question_text"],
                options=q["options"],
                correct_option_index=q["correct_option_index"],
                rationale=q["rationale"]
            )
            for q in raw_questions
        ]

        return QuizGenerateResponse(
            quiz_id=quiz_id,
            doc_id=req.doc_id,
            questions=formatted_questions,
            total_questions=len(formatted_questions)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error synthesizing quiz: {str(e)}"
        )

@router.post("/evaluate", response_model=QuizEvaluationResponse)
async def evaluate_quiz(req: QuizEvaluateRequest):
    """
    Evaluates student quiz answers, computes percentage, and returns detailed question-by-question rationale.
    """
    quiz_data = storage.get_quiz(req.quiz_id)
    if not quiz_data:
        raise HTTPException(
            status_code=404,
            detail=f"Quiz session '{req.quiz_id}' not found or has expired."
        )

    stored_questions = {q["question_id"]: q for q in quiz_data["questions"]}
    total_questions = len(stored_questions)
    if total_questions == 0:
        raise HTTPException(status_code=400, detail="Quiz contains no questions.")

    submitted_map = {ans.question_id: ans.selected_option_index for ans in req.answers}

    correct_count = 0
    breakdown: List[QuestionResult] = []

    for q_id, q_item in stored_questions.items():
        selected_idx = submitted_map.get(q_id, -1)
        correct_idx = q_item["correct_option_index"]
        is_correct = (selected_idx == correct_idx)
        if is_correct:
            correct_count += 1

        breakdown.append(
            QuestionResult(
                question_id=q_id,
                question_text=q_item["question_text"],
                selected_option_index=selected_idx,
                correct_option_index=correct_idx,
                is_correct=is_correct,
                rationale=q_item["rationale"]
            )
        )

    score_percentage = round((correct_count / total_questions) * 100, 1)
    passed = score_percentage >= 50.0

    if score_percentage >= 80:
        feedback = "Outstanding comprehension! You have demonstrated strong conceptual mastery of this unit."
    elif score_percentage >= 50:
        feedback = "Good performance! Review the rationales for questions you missed to solidify your understanding."
    else:
        feedback = "Conceptual review recommended. Revisit the uploaded notes and re-test using the tutor."

    return QuizEvaluationResponse(
        quiz_id=req.quiz_id,
        total_questions=total_questions,
        correct_count=correct_count,
        score_percentage=score_percentage,
        passed=passed,
        breakdown=breakdown,
        feedback_message=feedback
    )
