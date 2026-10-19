from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.services.pdf_service import pdf_service, PDFProcessingError
from backend.services.storage_service import storage
from backend.config import settings
from backend.schemas import DocumentUploadResponse, DocumentInfo
from typing import List

router = APIRouter(prefix="/api/documents", tags=["Documents"])

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Accepts a multipart/form-data PDF file upload, validates format and size,
    extracts clean text via PyMuPDF, and stores it in session memory.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type: Only standard PDF documents (.pdf) are accepted."
        )

    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to read uploaded file stream: {str(e)}"
        )

    try:
        pages_data, raw_text = pdf_service.validate_and_extract(
            file_bytes=content,
            filename=file.filename,
            max_size_mb=settings.MAX_UPLOAD_SIZE_MB
        )
    except PDFProcessingError as pe:
        raise HTTPException(status_code=422, detail=str(pe))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal document extraction error: {str(e)}"
        )

    doc_id = storage.store_document(
        filename=file.filename,
        pages_data=pages_data,
        raw_text=raw_text
    )

    preview_snippet = raw_text[:350].strip()
    if len(raw_text) > 350:
        preview_snippet += "..."

    return DocumentUploadResponse(
        doc_id=doc_id,
        filename=file.filename,
        pages=len(pages_data),
        char_count=len(raw_text),
        preview=preview_snippet,
        status="ready",
        message=f"Successfully extracted {len(pages_data)} pages ({len(raw_text)} characters)."
    )

@router.get("", response_model=List[DocumentInfo])
async def list_documents():
    """Returns list of currently uploaded and active study documents."""
    return storage.list_documents()

@router.get("/{doc_id}")
async def get_document_details(doc_id: str):
    """Retrieves document metadata, page excerpts, and parsing status."""
    doc = storage.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {
        "doc_id": doc["doc_id"],
        "filename": doc["filename"],
        "pages": doc["page_count"],
        "char_count": doc["char_count"],
        "upload_timestamp": doc["upload_timestamp"],
        "preview": doc["raw_text"][:600]
    }
