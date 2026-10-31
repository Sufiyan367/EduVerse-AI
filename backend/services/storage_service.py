import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "eduverse.db"

class StorageService:
    """
    Persistent SQLite3-backed storage service for EduVerse AI documents,
    quizzes, and evaluation records, featuring ACID compliance and fast in-memory caching.
    """
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        
        # In-memory fast cache synced with SQLite
        self._documents: Dict[str, Dict[str, Any]] = {}
        self._quizzes: Dict[str, Dict[str, Any]] = {}
        self._load_cache()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_database(self):
        """Creates the relational SQLite tables with schema constraints."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Documents Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    page_count INTEGER NOT NULL,
                    char_count INTEGER NOT NULL,
                    raw_text TEXT NOT NULL,
                    pages_json TEXT NOT NULL,
                    upload_timestamp TEXT NOT NULL
                );
            """)
            # Quizzes Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quizzes (
                    quiz_id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    questions_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (doc_id) REFERENCES documents (doc_id) ON DELETE CASCADE
                );
            """)
            # Quiz Evaluation Submissions Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quiz_evaluations (
                    eval_id TEXT PRIMARY KEY,
                    quiz_id TEXT NOT NULL,
                    score_percentage REAL NOT NULL,
                    correct_count INTEGER NOT NULL,
                    total_questions INTEGER NOT NULL,
                    passed INTEGER NOT NULL,
                    evaluated_at TEXT NOT NULL,
                    FOREIGN KEY (quiz_id) REFERENCES quizzes (quiz_id) ON DELETE CASCADE
                );
            """)
            # Knowledge Constellation Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document_concepts (
                    doc_id TEXT PRIMARY KEY,
                    concepts_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (doc_id) REFERENCES documents (doc_id) ON DELETE CASCADE
                );
            """)
            conn.commit()

    def _load_cache(self):
        """Preloads existing documents and quizzes from SQLite into in-memory dictionary cache."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Load documents
                cursor.execute("SELECT * FROM documents;")
                for row in cursor.fetchall():
                    self._documents[row["doc_id"]] = {
                        "doc_id": row["doc_id"],
                        "filename": row["filename"],
                        "page_count": row["page_count"],
                        "char_count": row["char_count"],
                        "raw_text": row["raw_text"],
                        "pages": json.loads(row["pages_json"]),
                        "upload_timestamp": row["upload_timestamp"]
                    }

                # Load quizzes
                cursor.execute("SELECT * FROM quizzes;")
                for row in cursor.fetchall():
                    self._quizzes[row["quiz_id"]] = {
                        "quiz_id": row["quiz_id"],
                        "doc_id": row["doc_id"],
                        "questions": json.loads(row["questions_json"]),
                        "created_at": row["created_at"]
                    }
        except Exception as e:
            print(f"[StorageService] Cache preload notice: {e}")

    def store_document(self, filename: str, pages_data: list[dict], raw_text: str) -> str:
        """Stores a parsed PDF document into SQLite database and memory cache."""
        doc_id = f"doc_{uuid.uuid4().hex[:10]}"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        pages_json = json.dumps(pages_data)

        # 1. Persist to SQLite
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO documents (doc_id, filename, page_count, char_count, raw_text, pages_json, upload_timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (doc_id, filename, len(pages_data), len(raw_text), raw_text, pages_json, timestamp))
            conn.commit()

        # 2. Update memory cache
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
        """Retrieves document metadata and extracted text by ID."""
        # Check cache first
        if doc_id in self._documents:
            return self._documents[doc_id]

        # Fallback query to SQLite
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM documents WHERE doc_id = ?;", (doc_id,))
            row = cursor.fetchone()
            if row:
                doc_obj = {
                    "doc_id": row["doc_id"],
                    "filename": row["filename"],
                    "page_count": row["page_count"],
                    "char_count": row["char_count"],
                    "raw_text": row["raw_text"],
                    "pages": json.loads(row["pages_json"]),
                    "upload_timestamp": row["upload_timestamp"]
                }
                self._documents[doc_id] = doc_obj
                return doc_obj
        return None

    def list_documents(self) -> list[Dict[str, Any]]:
        """Lists metadata summaries for all ingested documents."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT doc_id, filename, page_count, char_count, upload_timestamp FROM documents ORDER BY upload_timestamp DESC;")
            return [
                {
                    "doc_id": row["doc_id"],
                    "filename": row["filename"],
                    "pages": row["page_count"],
                    "char_count": row["char_count"],
                    "upload_timestamp": row["upload_timestamp"]
                }
                for row in cursor.fetchall()
            ]

    def store_quiz(self, doc_id: str, questions: list[dict]) -> str:
        """Stores a synthesized quiz into SQLite and cache."""
        quiz_id = f"quiz_{uuid.uuid4().hex[:10]}"
        created_at = time.time()
        questions_json = json.dumps(questions)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO quizzes (quiz_id, doc_id, questions_json, created_at)
                VALUES (?, ?, ?, ?);
            """, (quiz_id, doc_id, questions_json, created_at))
            conn.commit()

        self._quizzes[quiz_id] = {
            "quiz_id": quiz_id,
            "doc_id": doc_id,
            "questions": questions,
            "created_at": created_at
        }
        return quiz_id

    def get_quiz(self, quiz_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a quiz record by quiz ID."""
        if quiz_id in self._quizzes:
            return self._quizzes[quiz_id]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM quizzes WHERE quiz_id = ?;", (quiz_id,))
            row = cursor.fetchone()
            if row:
                quiz_obj = {
                    "quiz_id": row["quiz_id"],
                    "doc_id": row["doc_id"],
                    "questions": json.loads(row["questions_json"]),
                    "created_at": row["created_at"]
                }
                self._quizzes[quiz_id] = quiz_obj
                return quiz_obj
        return None

    def store_evaluation(self, quiz_id: str, score_percentage: float, correct_count: int, total_questions: int, passed: bool) -> str:
        """Stores student quiz score evaluation history into SQLite database."""
        eval_id = f"eval_{uuid.uuid4().hex[:10]}"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO quiz_evaluations (eval_id, quiz_id, score_percentage, correct_count, total_questions, passed, evaluated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (eval_id, quiz_id, score_percentage, correct_count, total_questions, 1 if passed else 0, timestamp))
            conn.commit()
        return eval_id

    def store_concepts(self, doc_id: str, concepts_data: dict) -> None:
        """Stores extracted Knowledge Constellation concepts and relationships into SQLite."""
        created_at = time.time()
        concepts_json = json.dumps(concepts_data)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO document_concepts (doc_id, concepts_json, created_at)
                VALUES (?, ?, ?);
            """, (doc_id, concepts_json, created_at))
            conn.commit()

    def get_concepts(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves stored Knowledge Constellation concepts and relationships for a document."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT concepts_json FROM document_concepts WHERE doc_id = ?;", (doc_id,))
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row["concepts_json"])
                except Exception:
                    return None
        return None

    def get_document_passage(self, doc_id: str, page_number: int = 1) -> Optional[Dict[str, Any]]:
        """Retrieves specific page/passage text with validated metadata."""
        doc = self.get_document(doc_id)
        if not doc:
            return None
        pages = doc.get("pages", [])
        total_pages = len(pages)
        if not pages:
            # Fallback for single raw text
            return {
                "doc_id": doc_id,
                "filename": doc["filename"],
                "page_number": 1,
                "total_pages": 1,
                "passage_text": doc.get("raw_text", ""),
                "char_count": len(doc.get("raw_text", ""))
            }
        
        target_idx = max(0, min(page_number - 1, total_pages - 1))
        page_info = pages[target_idx]
        return {
            "doc_id": doc_id,
            "filename": doc["filename"],
            "page_number": page_info.get("page_number", target_idx + 1),
            "total_pages": total_pages,
            "passage_text": page_info.get("text", ""),
            "char_count": len(page_info.get("text", ""))
        }

    def get_assessment_history(self, doc_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves persisted evaluation history joined with quizzes and documents."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT 
                    qe.eval_id,
                    qe.quiz_id,
                    q.doc_id,
                    COALESCE(d.filename, 'Unknown Document') AS filename,
                    qe.score_percentage,
                    qe.correct_count,
                    qe.total_questions,
                    qe.passed,
                    qe.evaluated_at
                FROM quiz_evaluations qe
                JOIN quizzes q ON qe.quiz_id = q.quiz_id
                LEFT JOIN documents d ON q.doc_id = d.doc_id
            """
            params = []
            if doc_id:
                query += " WHERE q.doc_id = ?"
                params.append(doc_id)
            query += " ORDER BY qe.evaluated_at DESC, qe.rowid DESC LIMIT 50;"
            cursor.execute(query, tuple(params))
            results = []
            for row in cursor.fetchall():
                results.append({
                    "eval_id": row["eval_id"],
                    "quiz_id": row["quiz_id"],
                    "doc_id": row["doc_id"],
                    "filename": row["filename"],
                    "score_percentage": float(row["score_percentage"]),
                    "correct_count": int(row["correct_count"]),
                    "total_questions": int(row["total_questions"]),
                    "passed": bool(row["passed"]),
                    "evaluated_at": row["evaluated_at"]
                })
            return results

    @property
    def document_count(self) -> int:
        """Returns the total number of registered documents in the SQLite database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM documents;")
            return cursor.fetchone()[0]

storage = StorageService()
