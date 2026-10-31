# EduVerse AI — Canonical Fullstack Application

**Path:** `EduVerse-AI-Complete/apps/fullstack`  
**Application Type:** FastAPI Backend + React 18 TypeScript Frontend  
**Database:** SQLite (`data/quicklearn.db`) with `sqlite-vec` vector indexing  

---

## Architecture Overview

This directory contains the production-grade canonical application for **EduVerse AI**:

- **`backend/quicklearn`**: Core FastAPI application package.
  - `api/`: REST and WebSocket endpoints (`auth.py`, `chat.py`, `sources.py`, `cards.py`, `quiz.py`, `system.py`, `dashboard.py`).
  - `pipeline/`: Ingestion, extraction (`document.py`), and boundary-aware chunking (`segment.py`).
  - `rag/`: Vector storage via `sqlite-vec` (`index.py`), hybrid retrieval with BM25 (`retrieve.py`).
  - `providers/`: Adapters for Google Gemini, Groq, OpenAI, Anthropic, Ollama, and local Mock mode.
- **`frontend/`**: Modern React 18 SPA built with Vite, Tailwind CSS, Lucide Icons, and KaTeX.
- **`data/`**: Runtime directory containing the SQLite database and uploaded document media files (gitignored).
- **`tests/`**: Comprehensive 146-test regression suite covering APIs, RAG, auth, FSRS flashcards, and multi-tenant isolation.

---

## Running Canonical Backend

From Windows Command Prompt:
```cmd
cd /d "S:\SY\SEM 3\MP\EduVerse-AI-repo\EduVerse-AI-Complete\apps\fullstack\backend"
set PYTHONPATH=.
python -m quicklearn --port 8080 --host 127.0.0.1 --data-dir "..\data"
```

## Running Regression Tests
```cmd
cd /d "S:\SY\SEM 3\MP\EduVerse-AI-repo\EduVerse-AI-Complete\apps\fullstack"
set PYTHONPATH=backend
pytest tests -v --tb=short
```

## Building Frontend
```cmd
cd /d "S:\SY\SEM 3\MP\EduVerse-AI-repo\EduVerse-AI-Complete\apps\fullstack\frontend"
npm ci
npm run build
```
Compiled static assets are copied to `backend/quicklearn/static` and served directly by FastAPI.
