# EduVerse AI — Grounded Academic Study & Active Recall Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-teal.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-0A2540.svg)](https://python.org)
[![FastAPI: 0.115+](https://img.shields.io/badge/FastAPI-0.115+-005F73.svg)](https://fastapi.tiangolo.com)
[![React: 18](https://img.shields.io/badge/React-18-61DAFB.svg?logo=react&logoColor=black)](EduVerse-AI-Complete/apps/fullstack/frontend/)
[![PyMuPDF: 1.24+](https://img.shields.io/badge/PyMuPDF-1.24+-0A9396.svg)](https://pymupdf.readthedocs.io/)
[![sqlite-vec](https://img.shields.io/badge/Vector%20Store-sqlite--vec-blue.svg)](https://github.com/asg017/sqlite-vec)
[![Test Suite: 48 Passed](https://img.shields.io/badge/Tests-48%20Passed%20(8%20Suites)-brightgreen.svg)](EduVerse-AI-Complete/apps/fullstack/backend/tests/)
[![Local LLM: Qwen3.5:4b](https://img.shields.io/badge/Local%20LLM-Qwen3.5%3A4b%20(RTX%203050)-7B2CBF.svg)](https://ollama.com)

> **Academic Classification:** B.Tech Artificial Intelligence & Data Science Mini-Project  
> **Institution:** Indira College of Engineering & Management (ICEM Pune)  
> **Affiliation:** Savitribai Phule Pune University (SPPU)  
> **Canonical Application Path:** `EduVerse-AI-Complete/apps/fullstack`  
> **Local Demo Gateway:** [http://127.0.0.1:8080](http://127.0.0.1:8080)

---

## 1. What is EduVerse AI?

**EduVerse AI** is an offline-first, evidence-grounded AI study companion inspired by Google NotebookLM. Built specifically for university engineering students, it enables learners to upload complex academic textbooks, lecture slides, and research papers, and interact with a document-grounded AI tutor.

Unlike generic conversational chatbots that hallucinate or rely on unverified web information, EduVerse AI operates under a **strict evidence contract**:
1. Every answer is grounded directly in the student's uploaded material.
2. Every factual statement is anchored to verbatim source excerpts with clickable page citations (e.g., `[1]`).
3. If an answer cannot be verified in the course material, the tutor **honestly abstains** rather than guessing.

---

## 2. Core Working Features

- **Multi-Tenant User Isolation:** Secure registration and login using Argon2id password hashing and JWT authentication. Study materials, notes, and vector indices are strictly isolated per student.
- **Academic PDF Layout Ingestion:** Geometric multi-column extraction with PyMuPDF, preserving two-column academic reading order, tables, and section headings.
- **Sparse & Scanned Slide Detection:** Individually identifies scanned slides and image-heavy pages (< 100 characters) for OCR/vision transcription without dropping pages.
- **Boundary-Aware Semantic Chunking:** Chunks respect physical page boundaries so citation markers always map to the exact physical page of the PDF.
- **Hybrid Search Engine:** Combines dense semantic vector retrieval (`sqlite-vec` + FastEmbed BGE) with sparse lexical search (SQLite FTS5 BM25) fused via Reciprocal Rank Fusion ($k=60$).
- **Relevance-Gated Reranker:** Evaluates retrieved excerpts with a strict relevance threshold ($> 0.15$), rejecting out-of-domain noise before prompt assembly.
- **Conversational Query Contextualization:** Automatically resolves pronouns and elliptical follow-up questions ("What are its two phases?", "Explain the second point") using chat history prior to retrieval.
- **Fail-Closed Citation Validation:** Model output is evaluated against retrieved segment IDs. Hallucinated citation markers are stripped, and ungrounded factual assertions are rejected.
- **Local Reasoning & GPU Acceleration:** Powered natively by `qwen3.5:4b` via local Ollama, offloaded to the NVIDIA GeForce RTX 3050 Laptop GPU (using ~3.7 GB VRAM). Executes complex multi-step reasoning (`think="high"`).
- **Privacy-Preserving Thinking Filter:** Model reasoning traces (`<think>...</think>`) are filtered from all user-facing responses and logs to protect student study privacy.
- **Evidence-to-Recall Learning Loop:** Transforms verified document excerpts into interactive multiple-choice quizzes and flashcards scheduled with the Free Spaced Repetition Scheduler (FSRS v6).
- **Citation Preview Thumbnails:** On-demand rendering of physical PDF page thumbnails (adapted from Cinnamon Kotaemon) for interactive citation preview.
- **Offline Mock Transparency:** When no external cloud API key is configured, the system operates in local offline mock mode, citing real excerpts and clearly flagging `is_mock=True` with no fake AI claims.

---

## 3. Upstream Technical Reference & Open-Source Attribution

EduVerse AI adapts core algorithmic patterns from the open-source RAG reference implementation **Cinnamon Kotaemon** (`Cinnamon/kotaemon`, Commit `9ad3e4e49aa35b8acddd235918a5d9753c1cfdf9`, Apache-2.0):
- **Spatial Bounding-Box Layout & Table Preservation:** Adapted from Kotaemon's `box.py` and `table.py`.
- **On-Demand Page Preview Thumbnails:** Adapted from Kotaemon's `pdf_loader.py`.
- **Inline Citation QA Verification:** Adapted from Kotaemon's `citation_qa_inline.py`.
- **Context Relevance Guard (0.15 threshold):** Adapted from Kotaemon's `simple.py`.

Full licensing terms and upstream notices are maintained in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

---

## 4. The Evidence-to-Recall Learning Loop

EduVerse AI is structured around a continuous cognitive workflow rather than open-ended chatting:

$$\text{Upload PDF} \longrightarrow \text{Query Tutor} \longrightarrow \text{Verify Citations} \longrightarrow \text{Generate Practice} \longrightarrow \text{Spaced Review}$$

```
   ┌────────────────────────────────────────────────────────┐
   │ 1. INGESTION: Multi-column extraction & boundary chunk │
   └───────────────────────────┬────────────────────────────┘
                               │
                               ▼
   ┌────────────────────────────────────────────────────────┐
   │ 2. RETRIEVAL: Hybrid sqlite-vec + BM25 with RRF        │
   └───────────────────────────┬────────────────────────────┘
                               │
                               ▼
   ┌────────────────────────────────────────────────────────┐
   │ 3. GROUNDING: LLM synthesis + fail-closed validation   │
   └───────────────────────────┬────────────────────────────┘
                               │
                               ▼
   ┌────────────────────────────────────────────────────────┐
   │ 4. EVIDENCE TRAIL: Clickable page excerpts [ID]        │
   └───────────────────────────┬────────────────────────────┘
                               │
                               ▼
   ┌────────────────────────────────────────────────────────┐
   │ 5. RECALL: Syllabus-anchored quizzes & FSRS flashcards │
   └────────────────────────────────────────────────────────┘
```

---

## 4. Technology Stack & Architecture

- **Backend Framework:** FastAPI (Python 3.11+), Uvicorn ASGI server.
- **Database & Persistence:** SQLite with SQLAlchemy 2.0 ORM and Alembic migrations.
- **Vector Storage:** `sqlite-vec` (native C-extension for vector similarity in SQLite).
- **Text Embeddings:** FastEmbed (`BAAI/bge-small-en-v1.5`, 384-dimensional dense vectors).
- **Lexical Search:** SQLite Full-Text Search (FTS5 BM25).
- **Document Processing:** PyMuPDF (`fitz`), Python-Docx, Python-PPTX.
- **Frontend Stack:** React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons, KaTeX math renderer.
- **Memory & Spaced Repetition:** FSRS v6 scheduler, Anki `.apkg` export.

---

## 5. Repository Structure

```text
EduVerse-AI/
├── EduVerse-AI-Complete/
│   └── apps/
│       └── fullstack/                   <-- Canonical Application Directory
│           ├── backend/                 <-- FastAPI backend package (quicklearn)
│           │   ├── quicklearn/
│           │   │   ├── api/             <-- API routes (auth, chat, sources, cards, quiz)
│           │   │   ├── db/              <-- SQLAlchemy models, enums, migrations
│           │   │   ├── pipeline/        <-- PDF extraction, OCR, segment chunking
│           │   │   ├── providers/       <-- LLM/Embedding adapters (Google, Groq, Ollama)
│           │   │   └── rag/             <-- sqlite-vec indexing, hybrid retrieval, rerank
│           │   └── pyproject.toml
│           ├── frontend/                <-- React 18 + Vite frontend
│           │   ├── src/                 <-- Components, routes, design system
│           │   └── package.json
│           ├── data/                    <-- Local SQLite database and storage (gitignored)
│           └── tests/                   <-- Canonical 146-test regression suite
├── docs/                                <-- Engineering and evaluation reports
│   ├── RAG_ENGINEERING_REPORT.md        <-- Full RAG audit, root causes, architecture
│   └── RAG_EVALUATION_REPORT.md         <-- 15-category academic PDF benchmark
├── start_app.bat                        <-- One-click Windows CMD launcher
├── start_app.ps1                        <-- One-click Windows PowerShell launcher
└── README.md                            <-- This file
```

---

## 6. Prerequisites

- **OS:** Windows 10/11 (64-bit), macOS, or Linux.
- **Python:** Python 3.11.x (recommended) or 3.10+.
- **Node.js (Optional):** Node.js 20+ (only required if modifying the frontend TypeScript source; pre-compiled static assets are bundled in `backend/quicklearn/static`).

---

## 7. Windows Command Prompt (CMD) Installation & Setup

Open **Command Prompt (cmd.exe)** as a regular user and execute:

### Step 1: Clone Repository
```cmd
cd /d "S:\SY\SEM 3\MP"
git clone https://github.com/Sufiyan367/EduVerse-AI.git
cd EduVerse-AI
```

### Step 2: Install Backend Dependencies
```cmd
python -m pip install --upgrade pip
pip install -e "./EduVerse-AI-Complete/apps/fullstack/backend[dev]"
```

### Step 3: (Optional) Build Frontend
If you make changes to the React frontend, compile the production bundle:
```cmd
cd EduVerse-AI-Complete\apps\fullstack\frontend
npm ci
npm run build
cd ..\..\..\..
```

---

## 8. Launching the Application

### Method A: One-Click Windows Script (Recommended)
From the repository root:
```cmd
start_app.bat
```
*(Or in PowerShell: `.\start_app.ps1`)*

### Method B: Direct Command Line
```cmd
cd /d "S:\SY\SEM 3\MP\EduVerse-AI-repo\EduVerse-AI-Complete\apps\fullstack\backend"
set PYTHONPATH=.
python -m quicklearn --port 8080 --host 127.0.0.1 --data-dir "..\data"
```

Once running, navigate your web browser to:
**`http://127.0.0.1:8080`**

---

## 9. How to Upload and Query a Study Document

1. **Register/Login:** Click **Create Account** to register a private student profile.
2. **Create Notebook / Upload Document:**
   - Go to **Library** $\rightarrow$ Click **Add Source** $\rightarrow$ Select an academic PDF file.
   - The document progress will transition from *Ingesting* $\rightarrow$ *Segmenting* $\rightarrow$ *Indexing* $\rightarrow$ *Ready*.
3. **Inspect Segments & Evidence:**
   - Open the document viewer to see extracted text, headings, and physical page numbers.
4. **Chat & Study:**
   - In the chat workspace, ask conceptual or factual questions (e.g., *"What is Two-Phase Locking?"*).
   - The response includes bracketed citations (`[1]`, `[2]`). Click any citation to immediately highlight the exact source excerpt and physical page.
5. **Ask Follow-up Questions:**
   - Query pronouns naturally (e.g., *"What are its two phases?"* or *"Explain the second one"*). The contextualizer resolves the subject automatically.
6. **Practice & Flashcards:**
   - Navigate to the **Quiz** tab to generate practice questions directly from the indexed document chunks.
   - Use the **Review** tab to review spaced repetition cards using FSRS ratings (Again, Hard, Good, Easy).

---

## 10. Configuring AI Providers & 3-Tier Routing

EduVerse AI features a strict 3-tier routing architecture that guarantees zero subscription cost and offline availability:

### Tier 1: Local Ollama (Primary — Recommended)
- **Model:** `qwen3.5:4b` running on `http://127.0.0.1:11434`.
- **GPU Acceleration:** Fully offloads to NVIDIA RTX 3050 (allocates ~3.7 GB VRAM).
- **Reasoning Control:** Supports `OLLAMA_THINK="high"` (options: `low`, `medium`, `high`, `off`).
- **Privacy Guarantee:** Internal `<think>...</think>` tokens are scrubbed from outputs.
- **Dedicated Health Check:** Real-time status at `http://127.0.0.1:8080/api/v1/health/llm`.

### Tier 2: Cloud Fallback Guard
- Cloud providers (Google Gemini, Groq, OpenAI, Anthropic) are **strictly blocked** by default (`ALLOW_CLOUD_FALLBACK=false`) to prevent unexpected external API usage.
- To enable cloud fallbacks, set `ALLOW_CLOUD_FALLBACK=true` in your `.env` or settings.

### Tier 3: Deterministic Local Mock
- When Ollama is offline and cloud fallback is disabled, EduVerse continues running without crashing, citing verified document segments in offline mock mode with `is_mock=True` transparently reported.

---

## 11. Running Automated Tests

All tests run from the canonical backend directory:

```cmd
cd /d "S:\SY\SEM 3\MP\EduVerse-AI-repo\EduVerse-AI-Complete\apps\fullstack\backend"
python -m pytest tests -v
```

The 48-test suite covers 8 specialized verification suites:

| Suite | File | Tests | Focus |
|---|---|:---:|---|
| **Autonomous Automation** | `test_autonomous_automation_engine.py` | 11 | Queue concurrency, leases, exponential backoff, background workers |
| **Local Ollama Inference** | `test_ollama_provider.py` | 4 | URL normalization, think token cleaning, payload parameters, live daemon |
| **DeepTutor P0 Adaptations** | `test_p0_adaptations_e2e.py` | 4 | Source manifest system note, prompt injection, verbatim citations, quiz evidence |
| **Comprehensive PDF Pipeline** | `test_pdf_pipeline_comprehensive.py` | 11 | Multi-column, tables, code/equations, scanned OCR, blank/corrupt PDFs, FTS5 |
| **Academic Workflow (Optional PG)**| `test_postgres_academic_workflow.py` | 3 | Course units, exam session simulation, mastery graph, vector retrieval |
| **Quiz Evidence Verification** | `test_quiz_evidence_verification.py` | 5 | Server-side quote matching, anti-hallucination rejector, hyphen resilience |
| **Quote Grounding & Normalization**| `test_quote_grounding.py` | 5 | Wrapped words, smart quotes/dashes, ligatures, cross-chunk boundaries |
| **Source Manifest System Note** | `test_source_manifest.py` | 5 | Inventory note rendering, user isolation, scope filtering, empty library |
| **Total** | **8 Test Suites** | **48** | **100% Passed** |

---

## 12. Troubleshooting Common Issues

| Issue / Error | Cause | Resolution |
| :--- | :--- | :--- |
| `sqlite3.OperationalError: no such table: segment_vectors` | SQLite database directory not found or uninitialized. | Ensure `--data-dir` points to `..\data` or export `$env:QUICKLEARN_DATA_DIR`. Run `python -m quicklearn` which auto-applies Alembic migrations. |
| `No language model is configured` | Routing standard tier is empty. | Go to **Settings $\rightarrow$ Routing** and select a configured provider (e.g., Google or Mock). |
| `Port 8080 already in use` | A previous backend server process is still running. | In CMD run `netstat -ano \| findstr :8080` and `taskkill /PID <PID> /F`, then re-run `start_app.bat`. |
| Follow-up chat queries lose topic | Naive retrieval query missing conversational context. | Resolved in `chat.py` via `_contextualize_query()`. Ensure you are running the canonical fullstack app. |
| Multi-column academic paper paragraphs mixed up | Standard vertical bounding-box sorting interleaves columns. | Resolved in `document.py` via `_sort_page_blocks()`. Re-upload or click **Reprocess** on the source. |

---

## 13. Security & Limitations

### Security Architecture
- Passwords hashed using Argon2id with salt.
- Server-side session invalidation via `revoked_tokens` table on logout.
- Multi-tenant data isolation: student documents and vector segments cannot be queried or resolved across user accounts.
- Encrypted local API key storage; secrets are masked in API responses and excluded from logging.

### Known Limitations
- **Scanned Math Handwriting:** Handwritten mathematical equations in low-contrast scans require multimodal vision LLM configuration.
- **Large Audio Files:** Local transcription without GPU uses chunked processing; cloud STT (Groq Whisper or Deepgram) is recommended for 1hr+ lecture recordings.
- **Single-Node SQLite:** Designed for single-student or local study-group laptop usage; not intended for high-concurrency cloud multi-region deployments.

---

## 14. Project Credits & Academic Attribution

- **Project Title:** EduVerse AI — Grounded Academic Study & Active Recall Platform
- **Degree:** Bachelor of Technology (B.Tech) in Artificial Intelligence & Data Science
- **Course:** Final Year Mini Project (Semester VI)
- **Institution:** Indira College of Engineering and Management (ICEM), Pune
- **Affiliation:** Savitribai Phule Pune University (SPPU)
- **Lead Developer:** Sufiyan Surve & Team
- **Department:** Department of Artificial Intelligence and Data Science
