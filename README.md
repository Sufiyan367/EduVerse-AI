# EduVerse AI — Grounded Academic Study & Active Recall Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-teal.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-0A2540.svg)](https://python.org)
[![FastAPI: 0.115+](https://img.shields.io/badge/FastAPI-0.115+-005F73.svg)](https://fastapi.tiangolo.com)
[![React: 18](https://img.shields.io/badge/React-18-61DAFB.svg?logo=react&logoColor=black)](EduVerse-AI-Complete/apps/fullstack/frontend/)
[![PyMuPDF: 1.24+](https://img.shields.io/badge/PyMuPDF-1.24+-0A9396.svg)](https://pymupdf.readthedocs.io/)
[![CI](https://github.com/Sufiyan367/EduVerse-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/Sufiyan367/EduVerse-AI/actions/workflows/ci.yml)

> **B.Tech Artificial Intelligence & Data Science Mini Project**  
> **Institution:** Indira College of Engineering & Management (ICEM Pune)  
> **Local Demo Gateway:** [http://127.0.0.1:8080](http://127.0.0.1:8080)

---

## 1. Project Overview

**EduVerse AI** is an offline-first academic study assistant inspired by Google NotebookLM. Designed for university students, it allows learners to upload course materials (lecture PDFs, notes, slides) and interact with an AI tutor that strictly answers questions based on the provided documents.

Every generated answer is anchored to verbatim text segments with clickable citations, preventing AI hallucinations. Students can also generate active-recall quizzes and flashcards scheduled using the Free Spaced Repetition Scheduler (FSRS) algorithm.

---

## 2. Technology Stack

- **Backend:** FastAPI, Python 3.11+, SQLAlchemy 2.0, Uvicorn, SQLite (`sqlite-vec` dense indexing).
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons, KaTeX (math rendering).
- **Document Processing:** PyMuPDF (`fitz`), Python-Docx, Python-PPTX.
- **RAG & Search:** Vector embeddings (`FastEmbed` / BAAI `bge-small-en-v1.5`), SQLite Full-Text Search (FTS5), hybrid retrieval.
- **Authentication:** Argon2id password hashing, JWT bearer tokens, server-side session revocation.
- **Memory & Spaced Repetition:** FSRS algorithm (v6), Anki deck (.apkg) export.

---

## 3. Main Features

1. **Authentication & Multi-Tenant Isolation:** Secure user registration, login with Argon2id hashing, session invalidation on logout and password reset. User materials and vector memory are fully tenant-isolated.
2. **Document Ingestion & Chunking:** Fast text extraction and layout preservation for multi-page PDFs, structured into searchable segment chunks.
3. **Source-Grounded AI Tutor (RAG):** Context-aware question answering. If a question cannot be answered from the uploaded material, the tutor refuses to guess and explicitly abstains.
4. **Traceable Citations:** All claims are tagged with bracketed citation markers (e.g., `[1]`) that link directly to the source page and passage.
5. **Interactive Quiz Generator:** Generates multiple-choice questions from syllabus chunks, grades student responses, and tracks learning progress.
6. **Flashcards & Spaced Repetition:** Auto-generates concept flashcards with spaced repetition scheduling based on difficulty ratings (Again, Hard, Good, Easy).
7. **Three-Column Notebook Workspace:** Left sidebar for source files, center reader/notes editor, right panel for AI study chat and tools.

---

## 4. Prerequisites

- **Operating System:** Windows 10/11, macOS, or Linux.
- **Python:** Version 3.11 or newer (Python 3.10+ supported).
- **Node.js (Optional):** Node.js 20+ (only required if modifying and recompiling the frontend; the repository includes pre-compiled static assets).

---

## 5. Installation

Clone the repository:

```bash
git clone https://github.com/Sufiyan367/EduVerse-AI.git
cd EduVerse-AI
```

Install backend dependencies:

```bash
python -m pip install --upgrade pip
pip install -e "./EduVerse-AI-Complete/apps/fullstack/backend[dev]"
```

*(Optional)* Install frontend dependencies if customizing UI:

```bash
cd EduVerse-AI-Complete/apps/fullstack/frontend
npm ci
npm run build
cd ../../../..
```

---

## 6. Starting the Application

On Windows, use the launcher script:

```powershell
.\start_app.ps1
```

Or using Command Prompt:

```cmd
start_app.bat
```

Alternatively, launch the backend directly:

```powershell
cd "EduVerse-AI-Complete/apps/fullstack/backend"
$env:PYTHONPATH="."
python -m quicklearn --port 8080 --host 127.0.0.1 --data-dir "../data"
```

The launcher will verify the Python runtime, verify the production frontend build, run database migrations, and open the application.

---

## 7. Accessing the Platform

Open your web browser and navigate to:

```text
http://127.0.0.1:8080
```

1. Click **Create Account** to register a new student account.
2. Sign in to access your private study dashboard.
3. Upload a PDF textbook or lecture slide in **Library** or **Workspace**.
4. Ask questions in the chat panel to see grounded answers with citations.

---

## 8. Configuring AI Providers

EduVerse AI works completely offline out-of-the-box using local FastEmbed embeddings and local deterministic responses. To connect a live cloud LLM:

1. Log in to your workspace.
2. Navigate to **Settings → Providers**.
3. Enter your API key for any supported provider:
   - **Google Gemini** (`gemini-1.5-flash`, `gemini-1.5-pro`)
   - **OpenAI** (`gpt-4o-mini`, `gpt-4o`)
   - **Anthropic Claude** (`claude-3-5-sonnet`)
   - **Groq** (`llama-3.1-70b`, `mixtral-8x7b`)
   - **Ollama** (Local self-hosted models like `llama3`, `mistral`, `deepseek-r1`)
4. In **Model Routing**, assign your chosen model for standard study chat and quiz generation.

API keys are encrypted at rest in the local SQLite database.

---

## 9. Running Automated Tests

Run the full canonical test suite (137 tests):

```powershell
cd "EduVerse-AI-Complete/apps/fullstack"
$env:PYTHONPATH="backend"
python -m pytest tests -v --tb=short
```

Run baseline project tests:

```powershell
$env:PYTHONPATH="."
python -m pytest tests -v --tb=short
```

---

## 10. Project Credits

- **Course:** B.Tech Mini Project (AI & Data Science)
- **Institution:** Indira College of Engineering & Management (ICEM Pune)
- **Developer:** Sufiyan Surve & Team
- **Department:** Department of Artificial Intelligence & Data Science
