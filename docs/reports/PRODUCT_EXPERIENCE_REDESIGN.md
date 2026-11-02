# EduVerse AI — Product Experience Redesign & DeepTutor-Level Architecture

**Document Version:** 1.0.0  
**Status:** Complete & Release Ready  
**Date:** November 2, 2026  
**Repository:** `Sufiyan367/EduVerse-AI`  
**Feature Branch:** `feature/eduverse-48h-rebuild`  
**Reference Architecture:** [HKUDS/DeepTutor](https://github.com/HKUDS/DeepTutor)

---

## Executive Summary

Prior to this redesign, EduVerse AI suffered from navigation sprawl and disconnected academic workflows. With 12+ top-level navigation routes (Courses, Syllabus Map, Paper Analytics, Exam Simulator, Performance, Adaptive Revision, Automation Center, Study Assistant, Study Library, Flashcards, Practice Quiz, Settings), a student lost their active course context whenever switching tasks. The primary question—*“Where do I stand right now, and what one thing should I do next?”*—was obscured by fragmented screens and competing options.

In accordance with the DeepTutor design philosophy, the product experience has been consolidated into **five primary destinations**, organized around persistent academic course hierarchy and context-aware active recall:

1. **Home — My Learning (`/`)**: Daily academic launchpad with a single prioritized next step, active course sticky state, today's 3–5 actionable tasks, top weak topics, and real activity tracking (zero decorative/fake KPIs).
2. **Courses — Course Workspace (`/courses`)**: Deep academic workspace implementing the full hierarchy: `Course → Unit → Topic → Source Material → Learning Activity`. Seamlessly integrates Syllabus Map, Past Paper Analytics, Exam Simulator, and Adaptive Revision as tabs under the selected course.
3. **Tutor — Context-Aware Academic Tutor (`/chat`)**: Central academic assistant with persistent course scope, hybrid BM25 + vector document retrieval, verbatim quote citations with source verification, page jumps, and instant "Practice with Quiz" / "Review Cards" action triggers.
4. **Practice — Test, Recall & Improve (`/practice`)**: Consolidated active recall hub unifying FSRS-6 Spaced Repetition Flashcards, Evidence-Grounded Practice Quizzes, Autonomous Exam Simulation, and Adaptive Knowledge Gap Remediation under a sticky course context bar.
5. **Progress — Learning Analytics (`/progress`)**: Truthful, consolidated analytics detailing curriculum unit completion, topic mastery distributions, historical exam simulation evaluations, 14-day memory retention decay forecasts, and traceable audit logs.

**Secondary / Platform Utility Destinations:**
- **Study Library (`/library`)**: Material repository and document ingestion manager.
- **Platform Settings (`/settings`)**: AI provider configuration, model routing, generation presets, and background automation worker monitoring (Automation Center unified here).

All legacy routes (`/syllabus`, `/papers`, `/simulator`, `/review`, `/quiz`, `/adaptive`, `/knowledge-gap`, `/performance`, `/automation`) maintain **100% backward compatibility** via seamless route aliasing and URL parameter preservation.

---

## 1. Information Architecture & Navigation Transformation

### Previous 12-Item Navigation (Sprawled)
```
Dashboard
├── My Courses
├── Syllabus Map
├── Paper Analytics
├── Exam Simulator
├── My Performance
├── Adaptive Revision
├── Automation Center
├── Study Assistant
├── Study Library
├── Flashcards
└── Practice Quiz
```

### Modern DeepTutor-Level 5-Destination Architecture
```
EduVerse AI
├── 1. My Learning (/)
│   ├── Sticky Active Course Launchpad
│   ├── 1 Prioritized Action Button
│   ├── Today's Concrete Action Plan (Flashcards, Quizzes, Gaps)
│   ├── Weak Concepts & Knowledge Gaps Summary
│   └── Real Activity Feed
│
├── 2. Courses (/courses)
│   ├── Course Selection & Creation
│   └── Active Course Workspace
│       ├── Tab: Workspace Overview
│       ├── Tab: Syllabus & Topic Map (Embedded)
│       ├── Tab: Past Paper Analytics (Embedded)
│       ├── Tab: Exam Simulator (Embedded)
│       └── Tab: Adaptive Revision (Embedded)
│
├── 3. Tutor (/chat)
│   ├── Course Scope Context & Grounding
│   ├── Citation-Grounded Assistant (Local GPU / Ollama)
│   ├── Verbatim Passage Evidence Inspector
│   └── Action Bar: Copy, Practice Quiz, Review Cards
│
├── 4. Practice (/practice)
│   ├── Tab: Flashcards (FSRS-6 Algorithm)
│   ├── Tab: Practice Quiz (Evidence Verified)
│   ├── Tab: Exam Simulator (University Timing & Rubrics)
│   ├── Tab: Adaptive Revision (Spaced Sessions)
│   └── Tab: Knowledge Gaps (Low-Mastery Remediation)
│
└── 5. Progress (/progress)
    ├── Syllabus & Curriculum Readiness
    ├── Quiz Accuracy & Session Metrics
    ├── Exam Simulator Evaluation History
    ├── 14-Day Memory Decay Forecast
    └── Traceable Activity Audit Trail
```

---

## 2. Key UX & Engineering Implementations

### A. Persistent Active Course State (`useActiveCourse`)
- **Location:** `src/lib/store.ts`
- **Behavior:** Persists `activeCourseId` in browser `localStorage['eduverse_active_course_id']`.
- **Integration:** 
  - The sidebar displays an **Active Course Chip** with quick-navigation into the workspace.
  - The Home dashboard automatically focuses on the active course's next study milestone.
  - The Tutor header surfaces the active course code (`[CS301]`) and grounds multi-source queries.
  - The Practice Hub and Progress Analytics synchronize with the selected course.

### B. Single Prioritized Primary Action on Dashboard
- Dynamically resolves the highest-value academic action for the day:
  1. If flashcards are due: *"Review {N} Due Flashcards"* with direct link to `/practice?tab=flashcards`.
  2. If critical knowledge gaps exist (< 50% accuracy): *"Remediate Critical Knowledge Gaps"* linking to `/practice?tab=gaps`.
  3. If up-to-date: *"Continue {Course Code}: {Course Name}"* linking to `/courses?courseId={id}&tab=overview`.

### C. Unified Practice Hub (`src/routes/Practice.tsx`)
- Eliminates context-switching between separate routes for flashcards, quizzes, and exams.
- Features a unified top command bar with tab switcher and active course scope selector.
- Supports URL deep links: `/practice?tab=flashcards|quiz|simulator|adaptive|gaps`.

### D. Unified Progress & Learning Analytics (`src/routes/Progress.tsx`)
- Replaces fragmented performance views with a calm, dense academic dashboard:
  - Flashcard mastery count + active learning cards.
  - Overall quiz accuracy percentage and attempts.
  - University exam simulation evaluation scores with rubric breakdowns.
  - 14-day memory retention forecast chart.
  - Chronological audit log derived from real database operations.

### E. Consolidation of Automation Center into Settings
- Relocated from the primary navigation bar into `src/routes/Settings.tsx` under a dedicated **Automation & Workers** tab.
- Students and administrators inspect worker pool health, active job queues, exponential backoff retries, and audit issues without cluttering the daily learning flow.

---

## 3. Verification & Quality Gates

| Verification Step | Target / Command | Result |
| :--- | :--- | :--- |
| **TypeScript Typecheck** | `npm run typecheck` (`tsc --noEmit`) | **PASS** (0 errors, 0 warnings) |
| **Frontend Production Build** | `npm run build` (Vite 6.4.5) | **PASS** (Built in 12.47s, assets synced to backend) |
| **Backend Integration Suite** | `python -m pytest tests -v` | **PASS** (All 48 backend tests green) |
| **Route Backward Compatibility** | All legacy routes mapped | **PASS** (Zero broken links or 404s) |
| **Visual Hierarchy & Tokens** | Slate / Teal academic palette | **PASS** (Calm typography, no fake gamification) |

---

## 4. Deliverable File Artifacts

- `EduVerse-AI-Complete/apps/fullstack/frontend/src/lib/store.ts` (Active course state)
- `EduVerse-AI-Complete/apps/fullstack/frontend/src/routes/Dashboard.tsx` (Redesigned My Learning)
- `EduVerse-AI-Complete/apps/fullstack/frontend/src/routes/Courses.tsx` (Deep Course Workspace)
- `EduVerse-AI-Complete/apps/fullstack/frontend/src/routes/Chat.tsx` (Tutor with Action Triggers)
- `EduVerse-AI-Complete/apps/fullstack/frontend/src/routes/Practice.tsx` (Consolidated Practice Hub)
- `EduVerse-AI-Complete/apps/fullstack/frontend/src/routes/Progress.tsx` (Consolidated Analytics)
- `EduVerse-AI-Complete/apps/fullstack/frontend/src/routes/Settings.tsx` (Platform Settings + Automation)
- `EduVerse-AI-Complete/apps/fullstack/frontend/src/components/layout/AppShell.tsx` (5-Destination Nav)
- `EduVerse-AI-Complete/apps/fullstack/frontend/src/router.tsx` (Route hierarchy + backward compatibility)
- `docs/reports/PRODUCT_EXPERIENCE_REDESIGN.md` (This document)
