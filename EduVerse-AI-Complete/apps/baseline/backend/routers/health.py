from fastapi import APIRouter
from backend.schemas import HealthResponse
from backend.config import settings
from backend.services.storage_service import storage

router = APIRouter(tags=["System"])

@router.get("/api/health", response_model=HealthResponse)
async def health_check():
    """System health check and diagnostic status."""
    return HealthResponse(
        status="healthy",
        project=settings.PROJECT_NAME,
        version=settings.VERSION,
        llm_provider=settings.LLM_PROVIDER,
        active_documents=storage.document_count
    )
