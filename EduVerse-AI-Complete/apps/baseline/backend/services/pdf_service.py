import io
import re
from typing import Tuple, List, Dict, Any
import pymupdf

class PDFProcessingError(Exception):
    """Custom exception raised during PDF parsing failures."""
    pass

class PDFService:
    @staticmethod
    def validate_and_extract(
        file_bytes: bytes,
        filename: str,
        max_size_mb: int = 25
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Validates the PDF bytes and extracts cleaned text page by page.
        Returns:
            pages_data: list of dicts with page_number and page_text
            full_text: concatenated cleaned text across all pages
        """
        # 1. Size Validation
        size_mb = len(file_bytes) / (1024 * 1024)
        if size_mb > max_size_mb:
            raise PDFProcessingError(
                f"File size ({size_mb:.2f} MB) exceeds maximum allowed limit of {max_size_mb} MB."
            )
        
        # 2. Check for empty or near-empty bytes
        if len(file_bytes) < 32:
            raise PDFProcessingError("The uploaded file is empty or too small to be a valid PDF.")
        
        # 3. Magic bytes check
        if not file_bytes.startswith(b"%PDF-"):
            raise PDFProcessingError(
                "Invalid file format: File header does not match standard PDF specification (%PDF-)."
            )

        # 4. Open document via PyMuPDF
        try:
            doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        except Exception as e:
            raise PDFProcessingError(f"Unable to read PDF file structure: {str(e)}")

        try:
            # 5. Check encryption
            if doc.is_encrypted:
                raise PDFProcessingError(
                    "The uploaded PDF is password-protected or encrypted. Please remove password protection and re-upload."
                )

            # 6. Check page count
            total_pages = len(doc)
            if total_pages == 0:
                raise PDFProcessingError("The uploaded PDF document contains 0 pages.")

            pages_data: List[Dict[str, Any]] = []
            extracted_chunks: List[str] = []

            for page_idx in range(total_pages):
                page = doc[page_idx]
                raw_page_text = page.get_text("text") or ""
                
                # Normalize line breaks and multiple whitespace
                cleaned_text = re.sub(r"[ \t]+", " ", raw_page_text)
                cleaned_text = re.sub(r"\n\s*\n+", "\n\n", cleaned_text).strip()

                pages_data.append({
                    "page_number": page_idx + 1,
                    "text": cleaned_text,
                    "char_count": len(cleaned_text)
                })
                if cleaned_text:
                    extracted_chunks.append(f"[Page {page_idx + 1}]\n{cleaned_text}")

            full_text = "\n\n".join(extracted_chunks).strip()

            # 7. Check if document has readable machine text
            if len(full_text) < 20:
                raise PDFProcessingError(
                    "No extractable text found in this PDF. It may consist entirely of scanned images or handwriting, which requires OCR."
                )

            return pages_data, full_text

        finally:
            doc.close()

pdf_service = PDFService()
