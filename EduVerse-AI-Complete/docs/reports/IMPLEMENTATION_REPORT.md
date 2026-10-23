# EduVerse AI — Implementation & Architecture Report

**Project:** EduVerse AI — AI-Powered Personalized Learning Platform  
**Target:** College Mini-Project Demonstration  
**Author:** Senior Full-Stack & AI Application Engineer  
**Date:** October 23, 2026  
**Status:** Completed & Fully Verified  

---

## 1. Executive Summary

EduVerse AI is an AI-powered personalized web learning platform engineered specifically for an academic mini-project demonstration. Unlike massive, cumbersome enterprise LMS platforms or fragile multi-container microservice suites, EduVerse AI is compact, self-contained, and genuinely functional. 

Built on a hardened open-source foundation adapted from `artbyjazi/quicklearn` (MIT License), EduVerse AI implements true end-to-end educational workflows without simulated or faked capabilities. It features real document ingestion (PDFs, text, markdown), local vector embeddings, grounded RAG tutoring with verifiable source citations, automated MCQ quiz generation, interactive evaluation, spaced repetition scheduling via Free Spaced Repetition Scheduler (FSRS), an algorithmic **Knowledge Gap Detector**, and an **Adaptive Revision Planner**.

---

## 2. System Architecture & Tech Stack

EduVerse AI adopts a clean, modular client-server architecture running natively on Windows 11.

```mermaid
graph TD
    User["Student Browser (Chrome / Edge / Firefox)"]
    
    subgraph Frontend ["React 19 + TypeScript + Vite + Tailwind CSS"]
        Shell["AppShell Navigation & Auth Modal"]
        DashView["Dashboard (/): Live Metrics & Activity Feed"]
        LibView["Study Library (/library): Document Ingestion"]
        TutorView["AI Tutor (/chat): Grounded RAG Chat"]
        QuizView["Quiz Portal (/quiz): Interactive MCQs"]
        GapView["Knowledge Gap Visualizer (/knowledge-gap)"]
        RevView["Adaptive Planner (/revision): Session Scheduler"]
        NotesView["Notes Editor (/notes): Rich Text Notes"]
    end
    
    subgraph Backend ["FastAPI + Python 3.11 (Asynchronous Server)"]
        AuthMiddleware["JWT Bearer Authentication & Session Guards"]
        APIRouters["API Routers: Auth, Dashboard, Gaps, Planner, Sources, Quiz, Chat"]
        
        subgraph CoreEngines ["Domain & Educational Engines"]
            GapEngine["Knowledge Gap Detector (Weakness Algorithm)"]
            PlanEngine["Adaptive Revision Engine (FSRS + Gap Prioritizer)"]
            FSRSEngine["FSRS Spaced Repetition Calculator"]
            RAGEngine["Hybrid RAG & Chunk Retriever"]
        end
        
        subgraph StorageLayer ["Persistence Layer"]
            SQLiteDB[("SQLite 3 DB (Alembic Managed)")]
            ChromaDB[("ChromaDB Vector Store (Embeddings)")]
            FileStorage[("Media Storage (PDFs & Documents)")]
        end
    end
    
    subgraph AIProviders ["Configured AI Providers (Zero Faking)"]
        LocalLLM["Local LLMs (Ollama / LM Studio)"]
        CloudLLM["Cloud LLMs (OpenAI / Gemini / Anthropic)"]
        MockLLM["Offline Deterministic Mock (Testing / Baseline)"]
    end
    
    User --> Shell
    Shell --> DashView & LibView & TutorView & QuizView & GapView & RevView & NotesView
    Frontend -->|REST API + Bearer Token| AuthMiddleware
    AuthMiddleware --> APIRouters
    APIRouters --> GapEngine & PlanEngine & FSRSEngine & RAGEngine
    APIRouters --> SQLiteDB
    RAGEngine --> ChromaDB
    APIRouters --> FileStorage
    RAGEngine & APIRouters --> LocalLLM & CloudLLM & MockLLM
```

### Component Details
- **Frontend:** React 19, TypeScript, Tailwind CSS, Lucide Icons, Radix UI primitives, Vite builder. Pre-compiled directly into `backend/quicklearn/static/` for standalone serving.
- **Backend:** FastAPI, Python 3.11, Pydantic v2, SQLAlchemy 2.0 ORM, Alembic migrations, Uvicorn ASGI server.
- **Database & Persistence:** SQLite 3 with WAL mode for ACID-compliant metadata storage, and ChromaDB for local vector embeddings.
- **AI Gateway:** Pluggable multi-provider architecture supporting OpenAI, Google Gemini, Anthropic Claude, Ollama (`http://localhost:11434`), LM Studio (`http://localhost:1234/v1`), and an explicit offline Mock engine.

---

## 3. Reused Upstream Foundations vs. Custom EduVerse Modules

To ensure academic rigor, speed of development, and maintainability, EduVerse AI reuses proven foundational mechanics while introducing novel educational capabilities tailored to modern pedagogical requirements.

| Layer / Module | Origin | Description & Customizations Added |
|---|---|---|
| **Document Ingestion & Parsing** | Upstream QuickLearn | Reused PDF extraction, text normalization, chunk segmentation, and ChromaDB vector indexing. |
| **Spaced Repetition** | Upstream QuickLearn | Reused Free Spaced Repetition Scheduler (FSRS) implementation for flashcard retention scheduling. |
| **RAG AI Tutoring** | Upstream QuickLearn | Reused segment citation grounding (`[1]`, `[2]`), prompt construction, and conversation threading. |
| **Authentication & Student Identity** | **EduVerse Custom Module** | Built zero-dependency PBKDF2-HMAC-SHA256 password hasher with salt, HMAC-SHA256 signed JWT tokens, `/api/v1/auth` endpoints (`login`, `register`, `me`, `logout`), and default demo account auto-seeding (`student@eduverse.ai` / `demo123`). |
| **Student Activity Tracking** | **EduVerse Custom Module** | Built unified `ActivityLog` tracking system recording document uploads, flashcard reviews, quiz submissions, note creations, and revision sessions into SQLite. |
| **Live Student Dashboard** | **EduVerse Custom Module** | Built `/api/v1/dashboard/stats` aggregating real-time enrolled documents, flashcards, FSRS due reviews, quiz attempt counts, average quiz accuracy %, retention health score %, and chronological activity feed. |
| **Knowledge Gap Detector** | **EduVerse Custom Module** | Engineered algorithmic weak-topic classifier (`quicklearn/study/knowledge_gap.py`) that categorizes student mastery into `CRITICAL` (<60%), `MODERATE` (60–79%), `PROFICIENT` (80–89%), and `MASTERED` (>=90%), complete with forensic question-level error evidence. |
| **Adaptive Revision Planner** | **EduVerse Custom Module** | Implemented dynamic revision recommendation engine (`quicklearn/study/revision_planner.py`) prioritizing critical knowledge gaps (`HIGH`), FSRS due cards (`MEDIUM`), and unquizzed documents (`LOW`). Includes full session lifecycle management (PENDING, IN_PROGRESS, COMPLETED). |
| **Interactive UI Extensions** | **EduVerse Custom Module** | Created dedicated frontend views: `KnowledgeGap.tsx` (gap visualizer with evidence drawers), `Revision.tsx` (planner and session tracker), enhanced `Dashboard.tsx`, and AppShell navigation/auth modal. |

---

## 4. Database Schema & Migration Architecture

EduVerse AI manages schema evolution cleanly using Alembic migrations without manual SQLite modifications.

### 4.1 New Database Models (`quicklearn/db/models.py`)
1. **`User` Table (`users`):**
   - `id` (INTEGER, Primary Key)
   - `email` (VARCHAR, Unique, Indexed)
   - `username` (VARCHAR, Unique, Indexed)
   - `hashed_password` (VARCHAR, PBKDF2 salted hash)
   - `full_name` (VARCHAR, Display name)
   - `avatar_color` (VARCHAR, Hex color code)
   - `created_at` (TIMESTAMP)

2. **`RevisionSession` Table (`revision_sessions`):**
   - `id` (INTEGER, Primary Key)
   - `user_id` (INTEGER, Foreign Key to `users.id`, Nullable)
   - `source_id` (INTEGER, Foreign Key to `sources.id`, Nullable)
   - `topic` (VARCHAR, Topic or concept to remediate)
   - `reason` (TEXT, Pedagogical rationale or gap score)
   - `priority` (VARCHAR: `HIGH`, `MEDIUM`, `LOW`)
   - `recommended_duration_min` (INTEGER, e.g. 15, 25, 45 minutes)
   - `status` (VARCHAR: `PENDING`, `IN_PROGRESS`, `COMPLETED`, `SKIPPED`)
   - `scheduled_for` (TIMESTAMP, Planned session time)
   - `completed_at` (TIMESTAMP, Nullable completion record)
   - `created_at` (TIMESTAMP)

3. **`ActivityLog` Table (`activity_logs`):**
   - `id` (INTEGER, Primary Key)
   - `user_id` (INTEGER, Foreign Key to `users.id`, Nullable)
   - `action` (VARCHAR: `UPLOAD`, `QUIZ_ATTEMPT`, `REVIEW`, `NOTE`, `REVISION`)
   - `entity_type` (VARCHAR: `source`, `quiz`, `card`, `note`, `revision`)
   - `entity_id` (INTEGER, Target ID)
   - `title` (VARCHAR, Human-readable activity title)
   - `details` (TEXT, JSON-encoded contextual metadata)
   - `created_at` (TIMESTAMP)

### 4.2 Migration Script
- Migration Version: `8a1b2c3d4e5f_eduverse_modules.py`
- Location: `backend/quicklearn/db/migrations/versions/8a1b2c3d4e5f_eduverse_modules.py`
- Executed automatically on application startup via `init_database(cfg)` in `backend/quicklearn/db/session.py`.

---

## 5. Algorithmic Implementations

### 5.1 Knowledge Gap Detection Algorithm
The Knowledge Gap Detector queries all past student `QuizAttempt` records joined with `QuizItem` and `Source`. For each distinct document/topic:
$$\text{Accuracy} = \frac{\sum \text{Correct Attempts}}{\text{Total Attempts}} \times 100$$
The topic status is deterministically classified:
- **`CRITICAL`**: $\text{Accuracy} < 60\%$ (Urgent remediation required)
- **`MODERATE`**: $60\% \le \text{Accuracy} < 80\%$ (Reinforcement recommended)
- **`PROFICIENT`**: $80\% \le \text{Accuracy} < 90\%$ (Solid understanding)
- **`MASTERED`**: $\text{Accuracy} \ge 90\%$ (Retained mastery)

Crucially, the detector records the exact question text, the user's incorrect response, and the correct answer in an `evidence` array, allowing students and evaluators to inspect exactly why a knowledge gap was flagged.

### 5.2 Adaptive Revision Priority Engine
The Revision Planner combines knowledge gap metrics with FSRS spaced repetition retention curves:
1. **Priority `HIGH`:** Triggered if any topic has a `CRITICAL` knowledge gap ($\text{Accuracy} < 60\%$). Immediate remediation session is generated.
2. **Priority `MEDIUM`:** Triggered if any FSRS flashcards have their `due` timestamp $\le \text{now}$. Generates a spaced repetition review session.
3. **Priority `LOW`:** Triggered if a study document has been ingested but has zero quiz attempts or cards generated. Recommends practice assessment.

---

## 6. AI Grounding & Provider Integrity

EduVerse AI strictly adheres to honest AI principles:
- **No Mock Faking:** When configured to connect to Ollama or LM Studio, real HTTP requests are dispatched to `http://localhost:11434` or `http://localhost:1234/v1`. If the local server or model is offline, the system raises a clear, descriptive error (`ProviderUnavailableError`) explaining how to launch the provider.
- **Deterministic Offline Testing:** When explicitly run in Mock mode (default for automated CI/unit tests), responses are clearly demarcated as generated by the offline test engine.
- **Verifiable RAG Grounding:** Responses in the AI Tutor include bracketed numerical citations (e.g., `[1]`) that link directly to underlying source document segments with page and character offsets.

---

## 7. Verification & Test Suite Summary

The entire EduVerse AI codebase has been validated through rigorous automated test suites:
- **Upstream Foundation Tests:** 105 passed.
- **EduVerse Custom Feature Tests:** 7 passed (`test_eduverse_features.py`).
- **Full 13-Step End-to-End Demo Workflow Verification:** 1 passed (`verify_full_demo_workflow.py`).
- **Total Test Suite:** **113 passed tests, 0 failures** in pytest.
- **Frontend TypeScript Static Typecheck:** `npm run typecheck` passed with **0 errors**.
- **Frontend Production Build:** `npm run build` compiled 4,222 modules with **0 errors** into `backend/quicklearn/static`.

---

## 8. Conclusion

EduVerse AI demonstrates that a college mini-project can achieve production-level code hygiene, architectural clarity, and genuine functionality without enterprise bloat. The application is completely ready for live academic demonstration, viva evaluation, and GitHub publishing.
