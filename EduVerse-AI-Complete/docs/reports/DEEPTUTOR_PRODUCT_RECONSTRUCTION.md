# EduVerse AI — DeepTutor-Level Interactive PDF Learning Workspace

**Date:** November 3, 2026  
**Repository:** `https://github.com/Sufiyan367/EduVerse-AI`  
**Branch:** `feature/eduverse-48h-rebuild`  
**Status:** **IMPLEMENTED, VERIFIED & PASSING (65/65 TESTS)**

---

## 1. Architectural Motivation & Objective

EduVerse AI was redesigned to close the gap between static document viewing and active academic mastery. Inspired by the architectural patterns in **DeepTutor** (`HKUDS/DeepTutor`), students should never have to switch across disconnected tools to understand complex textbooks and lecture slides.

Upon uploading a PDF, the system guides the student through four interconnected phases:
1. **Document Processing & Integrity Feedback:** Immediate visibility into extraction stages, page counts, segment counts, and unambiguous warnings for scanned/unreadable documents with one-click re-processing.
2. **Document Understanding:** Automatic extraction of structured hierarchical outlines (chapters, headings, sections, pages) and extracted key concepts.
3. **Interactive Studio Workspace:** A multi-mode learning workbench directly alongside the document reader:
   - **Grounded AI Tutor Chat:** Real-time conversational tutoring with verified, clickable passage citations that jump directly to source text segments.
   - **"Explain This Topic":** Deep pedagogical explanations supporting four distinct depths: *Principle*, *Analogy*, *Worked Example*, and *Compare*, backed by verified page citations.
   - **In-Workspace Interactive Quiz:** Document-grounded diagnostic quizzes with shuffled options, instant scoring, and citation feedback.
   - **Active Recall Flashcards:** Anki-compatible spaced repetition cards with full FSRS grading buttons (*Again*, *Hard*, *Good*, *Easy*).
   - **Practice Mode:** Interactive challenge problems with progressive hint reveals and model walkthroughs.
   - **Verifiable Document Progress:** Persistent database metrics computing real mastery ($0\text{--}100\%$) strictly from verified user interactions (passages studied, quiz accuracy, flashcard reviews). Zero fake metrics.

---

## 2. Technical Implementation Details

### 2.1 Backend Workspace & Pedagogical Endpoints (`quicklearn/api/sources.py`)

#### `GET /api/v1/sources/{source_id}/workspace`
Provides the frontend with all metadata required to render the full DeepTutor studio in a single round-trip:
- **`processing_state`**:
  - `status`: `READY` | `PROCESSING` | `FAILED` | `PARTIALLY_PROCESSED`
  - `stage`: `"complete"`, `"extracting_text"`, or error message
  - `is_unreadable`: Boolean flag set when $\le 15$ characters per page are extracted or OCR yields blank content.
  - `page_count` and `segment_count`: Exact counts from SQLite extraction records.
- **`outline`**:
  - Hierarchical outline parsed from document structure or segment summaries: title, level (1–3), page reference, and starting segment ID.
- **`concepts`**:
  - Extracted key concepts and topics identified in the source text.
- **`progress`**:
  - Truthful metrics calculated from database rows:
    - `passages_read` (distinct segments reviewed by the user)
    - `quiz_accuracy` (percentage of correct answers across document quizzes)
    - `cards_reviewed` (total active recall reviews)
    - `mastery_score` (weighted formula: $0.4 \times \text{quiz\_acc} + 0.3 \times \min(1, \text{cards}/10) + 0.3 \times \min(1, \text{passages}/20)$). Initial state is strictly $0.0\%$.

#### `POST /api/v1/sources/{source_id}/explain`
Generates deep pedagogical explanations strictly scoped to the document:
- **Request Body:** `{ "topic": str, "mode": "principle" | "analogy" | "worked_example" | "compare" }`
- **Output:**
  - `summary`: Clear, rigorous overview of the core concept.
  - `mode_explanation`: Deep dive tailored to the selected mode (e.g. step-by-step calculation for worked examples, structural comparisons for compare).
  - `definitions`: Key terminology defined cleanly.
  - `citations`: Verified page-level citations (`source_id`, `page`, `segment_id`, `snippet`) mapped directly to the document.

### 2.2 Concurrency-Safe Guided Learning Quiz Engine (`quicklearn/api/guided_learning.py`)

1. **Atomic Replay Protection with Single Winner:**
   - Evaluates quiz submissions within an atomic SQLite update:
     ```python
     rows_updated = db.query(GuidedQuizSession).filter(
         GuidedQuizSession.id == sess.id,
         GuidedQuizSession.consumed_at.is_(None)
     ).update({"consumed_at": now})
     if rows_updated == 0:
         raise HTTPException(status_code=409, detail="Quiz session has already been submitted.")
     ```
   - Concurrent duplicate submissions are safely rejected with `HTTP 409 Conflict`.
2. **Domain-Specific OS Subject Banks:**
   - Operating Systems is decoupled into fine-grained domains with 10 questions each:
     - `scheduling` (Round Robin, FCFS, SJF, SRTF, MLFQ)
     - `synchronization` (Semaphores, Mutexes, Peterson's Algorithm, Monitors, Bounded-Buffer)
     - `deadlock` (Banker's Algorithm, Resource Allocation Graphs, Coffman conditions)
     - `paging` / `memory` (TLB, page tables, fragmentation, demand paging)
3. **Step-by-Step Realistic Worked Examples:**
   - Removed canned placeholders. Generates authentic calculations:
     - Round Robin completion times and turnaround calculations with explicit Gantt sequences.
     - Producer-Consumer bounded-buffer code walkthrough using counting and binary semaphores.
     - Banker's Algorithm safe sequence derivation via $(Need \le Available)$ vectors.
     - 4KB page virtual address translation splitting into page number (higher 20 bits) and offset (lower 12 bits).
4. **Session Token Expiry:**
   - Unified to 1800 seconds (30 minutes) server-side and client-side.

### 2.3 Frontend DeepTutor Learning Studio (`frontend/src/routes/Source.tsx`)

Rebuilt the Source viewer into a full two-pane studio:
- **Left Pane:** Document reader with page navigation, zoom controls, and inline segment highlights.
- **Top Alert Banner:**
  - If `is_unreadable` is true or scanned without text, displays a high-visibility amber/red banner: *"Document May Be Scanned or Unreadable: Extracted text is sparse. Grounded AI explanations and quizzes may have limited context."* with a **"Retry Processing"** button calling `api.reprocessSource(id)`.
- **Right Studio Pane (7 Interactive Tabs):**
  1. **Outline:** Interactive table of contents. Clicking any entry smoothly jumps the document viewer to that exact page and highlights the segment.
  2. **Notes:** Document summaries, notes, and transcript view.
  3. **Explain:** Topic explainer with 4 selectable depth modes (*Principle*, *Analogy*, *Worked Example*, *Compare*). Citations are rendered as interactive badges that jump to source pages.
  4. **Quiz:** In-workspace 5-to-10 question multiple choice runner. Shuffled options, instant feedback, explanation breakdown, and direct jump to cited source text.
  5. **Cards:** Active recall flashcard deck. Front/back flip animation, and 4 FSRS spaced repetition rating buttons (*Again*, *Hard*, *Good*, *Easy*).
  6. **Practice:** Step-by-step problem challenges with progressive hint reveals and collapsible model solutions.
  7. **Progress:** Transparent learning analytics dashboard showing exact numbers of passages read, cards reviewed, quiz score, and overall document mastery percentage.

---

## 3. Verification & Test Matrix

The full fullstack test suite was executed against the active SQLite database:

```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-8.4.2
rootdir: S:\SY\SEM 3\MP\EduVerse-AI-repo\EduVerse-AI-Complete\apps\fullstack\backend
collected 65 items

tests/test_autonomous_automation_engine.py: 11 passed
tests/test_guided_learning_and_metrics.py: 17 passed
  - test_empty_course_readiness_insufficient_data PASSED
  - test_activity_vs_assessment_separation PASSED
  - test_partial_assessment_readiness_formula PASSED
  - test_exam_simulation_readiness_formula PASSED
  - test_topic_learning_lifecycle_flow PASSED
  - test_mastery_threshold_boundaries PASSED
  - test_quiz_token_is_opaque_and_unguessable PASSED
  - test_quiz_token_tampering_and_adversarial_submissions PASSED
  - test_answer_option_randomization_distribution PASSED
  - test_multi_subject_question_bank_coverage PASSED
  - test_concurrent_quiz_submissions_atomic_single_winner PASSED [NEW]
  - test_unsupported_topic_returns_explicit_unavailable PASSED
  - test_multitenant_rag_scope_isolation PASSED
  - test_manifest_multitenant_isolation PASSED
  - test_schedule_topic_revision_creates_task PASSED
  - test_user_isolation_blocks_cross_tenant_access PASSED
  - test_source_workspace_and_explain_endpoints PASSED [NEW]
tests/test_ollama_provider.py: 4 passed
tests/test_p0_adaptations_e2e.py: 4 passed
tests/test_pdf_pipeline_comprehensive.py: 11 passed
tests/test_postgres_academic_workflow.py: 3 passed
tests/test_quiz_evidence_verification.py: 5 passed
tests/test_quote_grounding.py: 5 passed
tests/test_source_manifest.py: 5 passed

============================= 65 passed in 46.16s =============================
```

Frontend compilation and build:
```
tsc --noEmit: 0 errors
vite build: built in 1.48s
copy-static.mjs: copied to backend/quicklearn/static
```

---

## 4. Conclusion

EduVerse AI now provides an authentic DeepTutor-grade academic document learning journey. All document states, processing indicators, pedagogical explanations, quiz grading mechanisms, and mastery metrics are fully verified, concurrency-safe, and backed by automated tests.
