import time
import uuid
from typing import Dict, Any, Optional

class StorageService:
    def __init__(self):
        # In-memory document storage: doc_id -> metadata and extracted text
        self._documents: Dict[str, Dict[str, Any]] = {}
        # In-memory quiz storage: quiz_id -> quiz data
        self._quizzes: Dict[str, Dict[str, Any]] = {}

    def store_document(self, filename: str, pages_data: list[dict], raw_text: str) -> str:
        doc_id = f"doc_{uuid.uuid4().hex[:10]}"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        self._documents[doc_id] = {
            "doc_id": doc_id,
            "filename": filename,
            "pages": pages_data,
            "page_count": len(pages_data),
            "raw_text": raw_text,
            "char_count": len(raw_text),
            "upload_timestamp": timestamp
        }
        return doc_id

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        return self._documents.get(doc_id)

    def list_documents(self) -> list[Dict[str, Any]]:
        return [
            {
                "doc_id": doc["doc_id"],
                "filename": doc["filename"],
                "pages": doc["page_count"],
                "char_count": doc["char_count"],
                "upload_timestamp": doc["upload_timestamp"]
            }
            for doc in self._documents.values()
        ]

    def store_quiz(self, doc_id: str, questions: list[dict]) -> str:
        quiz_id = f"quiz_{uuid.uuid4().hex[:10]}"
        self._quizzes[quiz_id] = {
            "quiz_id": quiz_id,
            "doc_id": doc_id,
            "questions": questions,
            "created_at": time.time()
        }
        return quiz_id

    def get_quiz(self, quiz_id: str) -> Optional[Dict[str, Any]]:
        return self._quizzes.get(quiz_id)

    @property
    def document_count(self) -> int:
        return len(self._documents)

storage = StorageService()
