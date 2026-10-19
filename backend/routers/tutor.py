from fastapi import APIRouter, HTTPException
from backend.schemas import (
    TutorQueryRequest,
    TutorQueryResponse,
    ConceptSimplifyRequest,
    ConceptSimplifyResponse
)
from backend.services.storage_service import storage
from backend.services.llm_service import llm_service

router = APIRouter(prefix="/api/tutor", tags=["Tutor"])

@router.post("/query", response_model=TutorQueryResponse)
async def query_tutor(req: TutorQueryRequest):
    """
    Submits a student doubt/question to the AI Tutor grounded in the specified document.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query text cannot be empty.")

    doc = storage.get_document(req.doc_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Study document '{req.doc_id}' not found. Please upload a PDF first."
        )

    try:
        result = llm_service.answer_query(
            document_context=doc["raw_text"],
            query=req.query
        )
        return TutorQueryResponse(
            doc_id=req.doc_id,
            query=req.query,
            answer=result["answer"],
            context_excerpt=result.get("context_excerpt"),
            grounded=result.get("grounded", True)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error executing tutor query: {str(e)}"
        )

@router.post("/simplify", response_model=ConceptSimplifyResponse)
async def simplify_concept(req: ConceptSimplifyRequest):
    """
    Generates an intuitive analogy and key takeaway points for a difficult concept.
    """
    if not req.concept.strip():
        raise HTTPException(status_code=400, detail="Concept cannot be empty.")

    doc = storage.get_document(req.doc_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Study document '{req.doc_id}' not found. Please upload a PDF first."
        )

    try:
        result = llm_service.simplify_concept(
            document_context=doc["raw_text"],
            concept=req.concept
        )
        return ConceptSimplifyResponse(
            doc_id=req.doc_id,
            concept=req.concept,
            analogy=result["analogy"],
            key_points=result["key_points"],
            syllabus_definition=result["syllabus_definition"],
            grounded=result.get("grounded", True)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating concept simplification: {str(e)}"
        )
