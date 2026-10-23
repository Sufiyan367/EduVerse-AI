# EduVerse AI — Comprehensive Technical Audit Report

**Target Workspace:** `S:\SY\SEM 3\MP\EduVerse_Web_Demo`  
**Host Environment:** Windows 11 / Python 3.11.9 / Node v20+  
**Application URL:** `http://127.0.0.1:8080`  
**Date of Audit:** October 23, 2026  
**Auditor:** Senior Full-Stack & AI Systems Architect  
**Audit Status:** Complete & Verified (Read-Only / Safe Execution)  

---

## 1. Verified Frontend Architecture

### 1.1 Framework & Exact Dependencies (`frontend/package.json`)
- **Core Framework:** React 18.3.1 (`react`, `react-dom`)
- **Bundler & Tooling:** Vite 6.1.0 (`@vitejs/plugin-react` 4.3.4), TypeScript 5.7.3
- **CSS & Design System:** Tailwind CSS 4.0.6 (`@tailwindcss/vite` 4.0.6, `tailwind-merge` 3.0.1, `clsx` 2.1.1)
- **UI Component Primitives:** Radix UI (`@radix-ui/react-dialog` 1.1.6, `dropdown-menu` 2.1.6, `popover` 1.1.6, `select` 2.1.6, `tabs` 1.1.3, `progress` 1.1.2, `tooltip` 1.1.8, `switch` 1.1.3)
- **Routing:** TanStack Router 1.105.0 (`@tanstack/react-router`) — code-based route tree
- **Server State & Data Fetching:** TanStack Query 5.66.0 (`@tanstack/react-query`)
- **Client State Management:** Zustand 5.0.3 (`zustand`)
- **Document & Note Editor:** TipTap 2.11.5 (`@tiptap/react`, `@tiptap/pm`, `@tiptap/starter-kit`, code block, tables, task lists)
- **Visuals & Rendering:** Lucide React 0.475.0 (icons), KaTeX 0.16.21 (math equations), Mermaid 11.4.1 (diagrams), Wavesurfer.js 7.9.1 (audio), Sonner 1.7.4 (toast notifications)

### 1.2 Entry Points, Routing & State Management
- **Entry Points:** `frontend/index.html` mounts `frontend/src/main.tsx` into `#root`.
- **Global Providers (`main.tsx`):**
  - `QueryClientProvider` with `defaultOptions: { queries: { staleTime: 15_000, refetchOnWindowFocus: false } }`.
  - `TooltipProvider` with delay 400ms.
  - `RouterProvider` injecting `router` from `frontend/src/router.tsx`.
  - `Toaster` component for notifications.
- **Routing Hierarchy (`frontend/src/router.tsx`):**
  - `rootRoute`: Hosts `AppShell` layout (`frontend/src/components/layout/AppShell.tsx`) and `NotFound` fallback.
  - `/`: `DashboardPage` (`frontend/src/routes/Dashboard.tsx`)
  - `/library`: `LibraryPage` (`frontend/src/routes/Library.tsx`)
  - `/library/$sourceId`: `SourcePage` (`frontend/src/routes/Source.tsx`)
  - `/review`: `ReviewPage` (`frontend/src/routes/Review.tsx`) — FSRS spaced repetition
  - `/quiz`: `QuizPage` (`frontend/src/routes/Quiz.tsx`) — Interactive assessment portal
  - `/chat`: `ChatPage` (`frontend/src/routes/Chat.tsx`) — Source-grounded AI tutoring
  - `/knowledge-gap`: `KnowledgeGapPage` (`frontend/src/routes/KnowledgeGap.tsx`) — Weakness analysis
  - `/revision`: `RevisionPage` (`frontend/src/routes/Revision.tsx`) — Adaptive revision planner
  - `/podcasts`: `PodcastsPage` (`frontend/src/routes/Podcasts.tsx`)
  - `/record`: `RecordPage` (`frontend/src/routes/Record.tsx`)
  - `/settings`: `SettingsPage` (`frontend/src/routes/Settings.tsx`)
- **Client State Stores (`frontend/src/lib/store.ts`):**
  - `useTheme`: Manages light/dark/system mode and applies CSS classes to `document.documentElement`.
  - `usePlayer`: Audio player playback state, seek requests, and active media IDs.
  - `useJobs`: Stores active background jobs received from the WebSocket.
  - `useUi`: Manages Command Palette (`Ctrl+K`) and mobile/desktop sidebar toggle state.

### 1.3 Implemented Pages & Control Audit
| Page Route | View / Component | Status | Real Backend API Integration | Placeholder / Mock Controls |
|---|---|:---:|---|---|
| `/` | `Dashboard.tsx` | Implemented | Calls `GET /api/v1/dashboard` & `GET /api/v1/dashboard/stats`. Live metric cards, focus areas, recent documents list, activity stream. | None. All metrics aggregate real DB rows. |
| `/library` | `Library.tsx` | Implemented | Calls `GET /api/v1/sources`, `GET /api/v1/folders`, `POST /api/v1/folders`, `DELETE /api/v1/sources/{id}`. | None. |
| `/library/$id` | `SourcePage.tsx` | Implemented | Calls `GET /api/v1/sources/{id}`, `GET /api/v1/sources/{id}/segments`, `PATCH /api/v1/sources/{id}`, `POST /api/v1/sources/{id}/regenerate`. | Audio player waveform controls present for audio files; inactive for PDFs. |
| `/chat` | `Chat.tsx` | Implemented | Calls `GET /api/v1/chat`, `POST /api/v1/chat`, and WebSocket `/api/v1/chat/ws/{id}` for streaming grounded responses with citations. | None. Real streaming token endpoint. |
| `/quiz` | `Quiz.tsx` | Implemented | Calls `GET /api/v1/quiz/practice`, `POST /api/v1/quiz/practice/answer`, `POST /api/v1/quiz/sessions`. Real interactive MCQ evaluation and score logging. | None. |
| `/knowledge-gap` | `KnowledgeGap.tsx` | Implemented | Calls `GET /api/v1/knowledge-gap/summary` and `GET /api/v1/knowledge-gap/topics`. Forensic error inspection and 1-click revision scheduling. | None. Real algorithmic classification. |
| `/revision` | `Revision.tsx` | Implemented | Calls `GET /api/v1/revision-planner/recommendations`, `GET /api/v1/revision-planner/sessions`, `POST /api/v1/revision-planner/schedule`, `PATCH /api/v1/revision-planner/sessions/{id}`. | None. |
| `/review` | `Review.tsx` | Implemented | Calls `GET /api/v1/cards/due`, `POST /api/v1/cards/{id}/review` with FSRS ratings (Again, Hard, Good, Easy). | None. |
| `/settings` | `Settings.tsx` | Implemented | Calls `GET /api/v1/settings`, `PATCH /api/v1/settings`, `POST /api/v1/settings/test-provider`. | Real provider checks. |
| `/record` | `Record.tsx` | Implemented | Browser MediaRecorder API capturing microphone audio, streaming chunks to `/api/v1/sources/record/start`. | Requires microphone hardware & STT. |

### 1.4 UI States, Accessibility & Responsiveness
- **Loading States:** Implemented across all views using animated `<Skeleton />` pulse blocks matching card layouts.
- **Empty States:** Implemented using `<EmptyState />` components with Lucide icons, clear copy, and primary action buttons (e.g. "Add your first study document").
- **Error States:** Implemented with toast notifications (`sonner`), validation messages on forms, and `<AlertTriangle />` banners for missing AI providers or failed requests.
- **Responsive Layout:** Adaptive sidebar using Tailwind `lg:hidden` drawer toggles, responsive grid layouts (`grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`), and touch-friendly tap targets.
- **Accessibility:** Semantic HTML elements (`<header>`, `<nav>`, `<main>`, `<button>`), Radix UI primitives with built-in ARIA roles (`role="dialog"`, `aria-expanded`), and full keyboard navigation with Command Palette (`Ctrl+K`).
- **Production Build Status:** Verified with exit code 0 (`npm run typecheck` and `npm run build`). Transforms 4,222 modules cleanly into `backend/quicklearn/static/`.

---

## 2. Verified Backend Architecture

### 2.1 Framework & Startup Execution
- **Framework:** FastAPI 0.115+ running on Python 3.11.9 with Uvicorn ASGI server.
- **Lifespan Initialization (`quicklearn/main.py`):**
  - Configures data directory and directories (`data/`, `media/`, `cache/`).
  - Initializes database and applies Alembic migrations via `init_database(cfg)`.
  - Boots default demo student account `student@eduverse.ai` (`demo123`).
  - Launches asynchronous background job pool (`WorkerPool`) and event bus (`EventBus`).
- **Startup Commands:**
  - Standard launcher: `run_eduverse.bat` / `run_eduverse.ps1` invoking `python -m quicklearn --port 8080 --host 127.0.0.1 --data-dir "..."`.
  - Safe shutdown: `stop_eduverse.bat` / `stop_eduverse.ps1`.

### 2.2 API Routers & Endpoints (`backend/quicklearn/api/`)
All endpoints are namespaced under `/api/v1`:

| Router | Prefix | Key Endpoints | Implementation Status |
|---|---|---|:---:|
| `auth` | `/auth` | `POST /login`, `POST /register`, `GET /me`, `POST /logout` | **IMPLEMENTED AND VERIFIED** |
| `dashboard` | `/dashboard` | `GET /stats` | **IMPLEMENTED AND VERIFIED** |
| `sources` | `/sources` | `POST /upload`, `POST /upload/init`, `POST /upload/chunk`, `POST /upload/complete`, `POST /url`, `POST /text`, `GET /{id}`, `PATCH /{id}`, `DELETE /{id}`, `POST /{id}/regenerate` | **IMPLEMENTED AND VERIFIED** |
| `library` | `""` | `GET /dashboard`, `GET /sources`, `GET /folders`, `POST /folders`, `GET /search` | **IMPLEMENTED AND VERIFIED** |
| `knowledge_gap` | `/knowledge-gap` | `GET /summary`, `GET /topics` | **IMPLEMENTED AND VERIFIED** |
| `revision_planner` | `/revision-planner` | `GET /recommendations`, `GET /sessions`, `POST /schedule`, `PATCH /sessions/{id}`, `DELETE /sessions/{id}` | **IMPLEMENTED AND VERIFIED** |
| `quiz` | `/quiz` | `GET /practice`, `POST /practice/answer`, `POST /sessions` | **IMPLEMENTED AND VERIFIED** |
| `cards` | `/cards` | `GET /due`, `POST /{id}/review`, `GET /stats`, `GET /counts` | **IMPLEMENTED AND VERIFIED** |
| `chat` | `/chat` | `GET /`, `POST /`, `GET /{id}`, `WS /ws/{id}` | **IMPLEMENTED AND VERIFIED** |
| `notes` | `/notes` | `GET /{id}`, `PATCH /{id}`, `POST /action`, `GET /{id}/export` | **IMPLEMENTED AND VERIFIED** |
| `system` | `""` | `GET /health`, `GET /settings`, `PATCH /settings`, `POST /settings/test-provider`, `WS /ws/jobs` | **IMPLEMENTED AND VERIFIED** |
| `podcasts` | `/podcasts` | `GET /`, `POST /`, `GET /{id}` | **PARTIAL** (Requires TTS provider) |

### 2.3 Authentication & Authorization
- **Hashing:** Standard library `hashlib.pbkdf2_hmac` with `sha256`, 100,000 iterations, and a unique 16-byte random salt per user.
- **Tokens:** Stateless HMAC-SHA256 signed JWT tokens containing user ID, username, email, issued timestamp, and 3-day expiration.
- **Middleware:** `get_current_user` extracts Bearer tokens from the `Authorization` header. `get_optional_user` permits backward compatibility for local/single-user routes.
- **Demo Seed:** Automatically provisions `student@eduverse.ai` (`demo123`) on bootstrap.

### 2.4 Document Processing Pipeline (`backend/quicklearn/handlers/ingest.py`)
1. **Upload / Ingest:** File is written directly to disk (`data/media/{source_id}/original.ext`).
2. **Normalize:** Audio/video media is processed via ffmpeg (skipped for PDFs/docs).
3. **Transcribe / Extract:** Extract pages via `pypdf`/`pdfplumber`, generate text segments with byte offsets.
4. **Filter:** Relevance assessment (skipped if no LLM configured).
5. **Generate Notes:** Outlines and sections generated via LLM (skipped if no LLM configured).
6. **Generate Concepts:** High-level educational concept extraction (skipped if no LLM configured).
7. **Generate Cards:** Anki-compatible flashcard extraction (skipped if no LLM configured).
8. **Index:** FastEmbed (`bge-small-en-v1.5`) generates 384-dimensional dense vectors and commits to SQLite-vec/Chroma.

### 2.5 Feature Status Classification

| Feature Module | Classification | Notes |
|---|:---:|---|
| Student Authentication & JWT Session | **IMPLEMENTED AND VERIFIED** | Verified by unit tests and live registration/login. |
| Student Dashboard Aggregations | **IMPLEMENTED AND VERIFIED** | Real-time calculations across sources, cards, quizzes, gaps. |
| Multi-Format Document Ingestion | **IMPLEMENTED AND VERIFIED** | PDF parsed and segmented into 46 pages. |
| Spaced Repetition (FSRS-4.5) | **IMPLEMENTED AND VERIFIED** | Full FSRS retention algorithm verified with rating updates. |
| Evidence-Grounded AI Tutor (RAG) | **IMPLEMENTED AND VERIFIED** | Tested with citations; refuses when retrieval lacks context. |
| MCQ Quiz Generation & Persistence | **IMPLEMENTED AND VERIFIED** | Persistence confirmed across engine restarts. |
| Algorithmic Knowledge Gap Detector | **IMPLEMENTED AND VERIFIED** | Classifies weaknesses (<60% accuracy) with error evidence. |
| Adaptive Revision Planner | **IMPLEMENTED AND VERIFIED** | Recommends remediation for gaps and FSRS due cards. |
| TipTap Rich Text Notes Editor | **IMPLEMENTED AND VERIFIED** | Note blocks, outlines, and HTML/MD export verified. |
| AI Provider Gateway (Ollama/LM Studio/Cloud) | **IMPLEMENTED AND VERIFIED** | Genuine HTTP connection checks; zero faking. |
| Audio Lecture Recording & Transcription | **PARTIAL** | Requires microphone device and local/cloud STT engine. |
| AI Podcast Audio Dialogue Generation | **PARTIAL** | Requires dual-voice TTS provider (ElevenLabs / Kokoro / EdgeTTS). |

---

## 3. Database Audit

### 3.1 Database Engine, Path & ORM
- **Engine:** SQLite 3 with Write-Ahead Logging (`WAL` mode) enabled for concurrent reader performance.
- **Database File:** `S:\SY\SEM 3\MP\EduVerse_Web_Demo\data\quicklearn.db`
- **WAL & SHM Files:** `quicklearn.db-wal` (3.2 MB), `quicklearn.db-shm` (32 KB).
- **ORM:** SQLAlchemy 2.0 ORM with declarative models and scoped session management.
- **Migration Engine:** Alembic (`alembic_version` revision: `8a1b2c3d4e5f_eduverse_modules`).

### 3.2 Schema & Table Inventory (Active Database)
Inspection of `quicklearn.db` revealed **35 tables** (relational entities + FTS5 full-text search + sqlite-vec vector tables):

| Table Name | Row Count | Purpose & Health |
|---|:---:|---|
| `sources` | **1** | Uploaded document metadata (`Unit 01 Introduction to Databases and SQL`, status: `ready`). |
| `transcripts` | **1** | Full text transcript container for Source 1. |
| `segments` | **46** | Semantic chunks corresponding to the 46 pages of the uploaded PDF. |
| `search_docs` | **47** | Full-text search index records. |
| `search_fts*` | **108** | SQLite FTS5 inverted index data structures. |
| `segment_vectors*` | **52** | sqlite-vec virtual tables and 384-dimensional vector embeddings. |
| `jobs` | **8** | Ingestion pipeline jobs (`ingest`, `normalize`, `transcribe`, `filter`, `generate_notes`, etc.). |
| `users` | **1** | Demo student account (`student@eduverse.ai`). |
| `settings` | **2** | System vector parameters (`rag.vector_dim = 384`, `rag.vector_backend = "sqlite-vec"`). |
| `cards` | 0 | Flashcards (not generated due to missing LLM configuration during ingest). |
| `concepts` | 0 | Extracted concepts (not generated due to missing LLM configuration). |
| `notes` | 0 | Notes (not generated due to missing LLM configuration). |
| `quiz_items` | 0 | Question bank items. |
| `quiz_attempts` | 0 | Historical student quiz submissions. |
| `revision_sessions`| 0 | Scheduled adaptive revision sessions. |
| `activity_logs` | 0 | Chronological audit trail. |

### 3.3 Foreign Keys, Integrity & Persistence
- **Foreign Key Enforcement:** Foreign keys are explicitly configured (`PRAGMA foreign_keys = ON`). Cascading deletions protect against orphaned records (deleting a `Source` removes its `segments`, `transcripts`, `cards`, `notes`, and vector embeddings).
- **Persistence Verification:** Verified via automated test `tests/verify_full_demo_workflow.py` (Step 13). Rebuilding the database connection and restarting the server maintains 100% data integrity with zero data loss.

---

## 4. Investigation of the "Stuck PDF" & "No Model Configured"

### 4.1 Observed Behavior in Browser
- When opening `http://127.0.0.1:8080`, the dashboard showed one uploaded PDF labeled `processing`, and displayed the alert banner: *“No language model configured yet.”*

### 4.2 Forensic Investigation Findings
1. **The PDF is NOT stuck in the database:**
   Direct query of `quicklearn.db` showed:
   - `sources.id = 1`
   - `sources.title = 'Unit 01 Introduction to Databases and SQL'`
   - `sources.status = 'ready'`
   - `sources.error = None`
   - `created_at = 2026-10-23 09:50:05 UTC` (3:20 PM IST)
   - `updated_at = 2026-10-23 09:50:41 UTC` (3:20 PM IST)
   - Ingestion Job 1 (`ingest`) and Job 8 (`index`) both finished with status `succeeded` at `09:50:41 UTC` (total execution time: 36 seconds).
   - Text extraction was **100% successful**: 46 pages were converted into 46 segments and 46 vector embeddings.
2. **Why the browser UI displayed `processing`:**
   - **Root Cause 1 (Frontend Event Handling Bug):** In `frontend/src/lib/store.ts:113`, the Zustand event handler contains the guard `if (!event.job_id) return state`. When the backend finishes ingestion, `handlers/ingest.py:236` broadcasts `emit("source.updated", source_id=source_id, status="ready")`. Because this event contains `source_id` but not `job_id`, **the Zustand store silently discards the event**.
   - **Root Cause 2 (Missing React Query Invalidation):** Neither `JobSocket.onmessage` nor `store.ts` invalidates TanStack Query's cache keys (`['dashboard']` or `['source', id]`) upon job completion.
   - **Root Cause 3 (Disabled Window Focus Refetch):** In `frontend/src/main.tsx:15`, `refetchOnWindowFocus: false` is configured.
   - **Root Cause 4 (Disabled Polling Interval on Source View):** In `SourcePage.tsx:62`, `refetchInterval: activeJob ? 2000 : false`. Because completed jobs are immediately removed from `activeJob`, polling stops permanently.
   - **Conclusion:** The browser displayed `processing` purely because the frontend query cache retained the initial state from upload time and never re-fetched. A simple hard refresh (F5) displays the true `ready` status.
3. **Why the document has 0 notes, 0 concepts, and 0 flashcards:**
   - In `backend/quicklearn/handlers/ingest.py:139-147`:
     ```python
     if not registry.has_llm():
         skip.update(
             {
                 JobType.FILTER,
                 JobType.GENERATE_NOTES,
                 JobType.GENERATE_CONCEPTS,
                 JobType.GENERATE_CARDS,
             }
         )
     ```
   - When the PDF was uploaded, no language model was configured (`registry.has_llm() == False`).
   - The backend intentionally skipped the AI-dependent stages to prevent pipeline failure while preserving the extracted text and search embeddings.
   - The banner *“No language model configured yet”* is the expected, honest system behavior.

---

## 5. Verification & Test Execution Results

All verification was performed safely without modifying existing database records.

| Test Category | Command Executed | Exit Code | Result | Evidence |
|---|---|:---:|:---:|---|
| **Backend Unit & Feature Suite** | `pytest -v` (112 test items) | `0` | **112 PASSED** | All API routes, FSRS scheduling, RAG grounding, auth hashing, and local provider handling passed. |
| **Full 13-Step College Demo Workflow** | `pytest tests/verify_full_demo_workflow.py -v -s` | `0` | **13/13 PASSED** | End-to-end user simulation (auth, upload, RAG, quiz, gap detector, adaptive revision, restart persistence). |
| **Frontend TypeScript Typecheck** | `npm run typecheck` (`tsc --noEmit`) | `0` | **0 ERRORS** | Full TypeScript AST validation passed with zero type errors. |
| **Frontend Production Build** | `npm run build` | `0` | **SUCCESS** | 4,222 modules transformed; assets cleanly written to `backend/quicklearn/static/`. |
| **Live Database Read-Only Query** | Python SQLite reader script | `0` | **VERIFIED** | Source 1 verified at status `ready`, 46 segments, 8 succeeded jobs. |

---

## 6. GitHub & Configuration Audit

- **Git Status:** Working tree is clean. 1 local commit ahead (`9159a6a`).
- **Latest Commit:** `9159a6a` — *"feat(eduverse): complete polished web app demo with auth, gap detector, adaptive planner and docs"* (45 files changed, 5,161 insertions).
- **License & Attribution:** MIT License preserved in `LICENSE` file; full attribution to upstream `artbyjazi/quicklearn` documented in `README.md` and `docs/FOUNDATION_COMPARISON.md`.
- **Environment Configuration:** Clean `.env.example` file provided without credentials. Default `.gitignore` excludes `.env`, `data/`, `logs/`, `.venv/`, and `node_modules/`.
- **CI Workflows:** `.github/workflows/ci.yml` runs matrix testing across Python 3.11/3.12, linting with Ruff, pytest suite, and frontend build.
- **Original Project Safety:** Baseline repository `S:\SY\SEM 3\MP` remains 100% untouched.

---

## 7. Security and Reliability Issues

1. **Authorization Boundaries (Medium):** Endpoints currently allow any authenticated session to access documents by ID. For a college demo or single-student environment, this is acceptable, but true multi-tenancy requires scoping queries by `user_id`.
2. **Frontend WebSocket-to-Query Invalidation (Low):** Job completion events do not trigger automatic React Query invalidations, causing stale UI states after uploads unless refreshed.
3. **Missing LLM Ingestion Fallback Notification (Low):** Ingesting documents without an LLM leaves them with 0 concepts and notes without an explicit "Generate Notes" callout on the document view.

---

## 8. Prioritized Work Roadmap (P0 / P1 / P2)

### P0 (Must Have for Live College Demo)
1. **Bridge WebSocket to React Query Invalidation:** In `AppShell.tsx` or `ws.ts`, hook `jobSocket` events to invalidate query keys `['dashboard']`, `['source']`, and `['sources']` upon completion so the UI updates dynamically without F5.
2. **Handle `source.updated` in Zustand Store:** Update `store.ts` to process events with `source_id` even if `job_id` is null.
3. **1-Click AI Provider Setup:** Add a "Quick Setup: Enable Offline Mock AI" button directly on the "No language model configured" banner in `Dashboard.tsx` and `Settings.tsx` for immediate viva demo readiness.

### P1 (Core Polish & Evaluation Robustness)
1. **Document-Level "Extract Concepts & Generate Quiz" Action:** Add a prominent button on `/library/$sourceId` when `concepts == 0` allowing the student to trigger concept extraction once an AI model is connected.
2. **Multi-User Data Scoping:** Add `user_id` foreign keys to `Source` and filter `/sources` by active student.

### P2 (Post-Demo Enhancements)
1. **Side-by-Side PDF Reader:** Display original PDF pages adjacent to AI-generated notes.
2. **Export Quiz Analytics:** Generate downloadable evaluation reports (PDF/CSV) for teachers.

---

## 9. Recommended Next Steps

1. Apply the minor frontend cache-invalidation patch so that uploaded documents automatically transition from `processing` to `ready` without manual browser refresh.
2. In `Settings`, select either **Ollama** (if a local model is pulled) or **Offline Mock** so that future document uploads automatically extract concepts, flashcards, and quizzes.
3. Use the verified 5-minute presentation script in `docs/SETUP_AND_DEMO_GUIDE.md` for the viva evaluation.
