import io
import pytest
import pymupdf
from backend.services.pdf_service import pdf_service, PDFProcessingError

def create_sample_pdf_bytes(text: str = "Machine Learning Course Notes. Unit 4: Supervised Learning.") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

def test_valid_pdf_extraction():
    sample_text = "Linear Regression models linear relationships. Logistic Regression models probabilities."
    pdf_bytes = create_sample_pdf_bytes(sample_text)
    
    pages, full_text = pdf_service.validate_and_extract(pdf_bytes, "notes.pdf", max_size_mb=25)
    
    assert len(pages) == 1
    assert "Linear Regression" in full_text
    assert "Logistic Regression" in full_text

def test_empty_bytes_rejected():
    with pytest.raises(PDFProcessingError) as exc_info:
        pdf_service.validate_and_extract(b"", "empty.pdf")
    assert "empty" in str(exc_info.value).lower()

def test_corrupt_file_rejected():
    corrupt_bytes = b"This is not a real PDF file header."
    with pytest.raises(PDFProcessingError) as exc_info:
        pdf_service.validate_and_extract(corrupt_bytes, "corrupt.pdf")
    assert "specification" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

def test_size_limit_enforced():
    pdf_bytes = create_sample_pdf_bytes("Small text")
    # Test setting max_size_mb to 0.000001 (very small limit)
    with pytest.raises(PDFProcessingError) as exc_info:
        pdf_service.validate_and_extract(pdf_bytes, "large.pdf", max_size_mb=0.0001)
    assert "exceeds maximum allowed limit" in str(exc_info.value)
