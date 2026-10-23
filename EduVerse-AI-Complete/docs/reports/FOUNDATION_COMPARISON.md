# EduVerse AI — Foundation Comparison & Architecture Selection

**Project:** EduVerse AI — Polished, Fully Functional College Mini-Project Demo  
**Auditor:** Senior Full-Stack & AI Application Engineer  
**Date:** October 23, 2026  
**Status:** Evaluation Completed & Winner Selected  

---

## 1. Executive Summary & Evaluation Criteria

The objective is to select the optimal open-source foundation for **EduVerse AI**, a compact, polished, and genuinely functional AI-powered web learning application tailored for an academic mini-project demonstration.

### Key Constraints & Requirements:
1. **Web-Based Application:** Must run as a responsive web application accessible via standard web browsers (Chrome, Edge, Firefox, Brave) on desktop and mobile. Desktop-only applications (e.g. Tauri/Electron requiring containerized sandboxes or native window managers) are disqualified.
2. **Compact & Self-Contained:** Avoid enterprise-grade multi-service monsters (Kubernetes, Redis clusters, multi-tenant Kafka/Celery, Turborepo microservice suites) that exceed college demo scope and risk reliability failures.
3. **Genuine Educational Workflows:** Must support document ingestion (PDFs), AI tutoring grounded in real source text, quiz generation and scoring, spaced repetition, knowledge gap tracking, and student notes.
4. **Honest AI & Error Handling:** Must integrate real LLM providers (Ollama, LM Studio, OpenAI, Gemini) and fail transparently without fabricating mock responses.
5. **Permissive Licensing:** Must permit adaptation and academic presentation with clear attribution (e.g., MIT or Apache 2.0).
6. **Windows 11 Native Execution:** Must run smoothly on Windows without requiring WSL2, Docker, or complex cloud dependencies.

---

## 2. Comparative Matrix of Candidate Foundations

| Metric / Dimension | Candidate 1: OpenMAIC | Candidate 2: SkillCoco | Candidate 3: ClassroomIO | Candidate 4: OpenTutor | Selected Foundation: QuickLearn |
|---|---|---|---|---|---|
| **Repository** | `THU-MAIC/OpenMAIC` | `skillcoco/skillcoco` | `classroomio/classroomio` | `zijinz456/OpenTutor` | `artbyjazi/quicklearn` |
| **License** | AGPL-3.0 (Copyleft) | MIT | AGPL-3.0 (Copyleft) | Apache-2.0 | **MIT (Permissive)** |
| **Primary Platform** | Web App (Full-stack) | **Desktop-Only (Tauri/Rust)** | Web App (Enterprise LMS) | Web App (Multi-service) | **Web App (FastAPI + React)** |
| **Tech Stack** | Node.js + PostgreSQL | Rust + Tauri + xterm.js | SvelteKit + Hono + Drizzle + Redis | FastAPI + Next.js + Chroma | **FastAPI + React/TS + SQLite + Chroma** |
| **Architecture Scope** | Multi-Agent Classroom / Slides Generator | Sandboxed Terminal Coding Labs | Enterprise B2B LMS / Course Authoring | 12-block Modular Adaptive Workspace | **Compact Student Study & AI Tutoring App** |
| **Container / Sandbox Dependency** | Optional Docker | **Mandatory Docker Sandboxes** | **Mandatory Docker / Redis / PG** | Docker / Multiple Node processes | **Zero (Native Windows Python + Vite)** |
| **Student Study Workflows** | Teacher-centric slides/simulations | Hands-on terminal coding exercises | Enterprise training / certifications | General adaptive learning | **PDFs, FSRS Spaced Repetition, Quizzes, Notes, RAG Chat** |
| **Windows Demo Reliability** | Moderate (PostgreSQL config) | Poor (Tauri + Docker lab daemon on Win11) | Low (Heavy microservices, Redis, Drizzle) | Moderate (Next.js SSR + Playwright) | **High (Single-command launch, 105 passed tests)** |
| **Fit for College Demo** | Poor (Not student-focused) | Disqualified (Desktop-only) | Poor (Massive enterprise LMS) | Moderate (Overly complex UI blocks) | **Excellent (Clean, compact, fully verified)** |

---

## 3. Detailed Audit of Each Candidate

### 3.1 Candidate 1: OpenMAIC (`THU-MAIC/OpenMAIC`)
- **Strengths:** High academic pedigree from Tsinghua University. Demonstrates sophisticated multi-agent orchestration for dynamic slide presentations and animated avatars.
- **Weaknesses:**
  - **Scope Mismatch:** Focuses on *generating presentation slides, TTS voiceovers, and simulated classroom scenes for teachers*, rather than serving as an individual student's study portal with flashcard schedules, revision planning, and notes.
  - **License Restriction:** AGPL-3.0 imposes strict viral copyleft terms.
  - **Heavyweight Dependencies:** Requires dedicated PostgreSQL database, background streaming queues, and multi-agent pipeline runners.
- **Verdict:** **REJECTED.** Misaligned with student study portal requirements; too presentation-heavy.

---

### 3.2 Candidate 2: SkillCoco (`skillcoco/skillcoco`)
- **Strengths:** Excellent algorithmic core combining Bayesian Knowledge Tracing (BKT) and SM-2 spaced repetition. MIT licensed.
- **Weaknesses:**
  - **Desktop-Only Architecture:** Built with Rust, Tauri, and native operating system bindings. Adapting it to a browser-based web application would require discarding the entire frontend shell and Tauri IPC bridge.
  - **Docker Requirement:** Requires Docker desktop to run terminal sandbox containers for code execution.
- **Verdict:** **DISQUALIFIED.** Explicitly violates the constraint against desktop-only applications requiring major architectural rewrites.

---

### 3.3 Candidate 3: ClassroomIO (`classroomio/classroomio`)
- **Strengths:** Extremely mature enterprise platform with course builder, student progress tracking, and professional UI.
- **Weaknesses:**
  - **Enterprise Bloat:** Designed as a replacement for enterprise platforms like Moodle, Thinkific, and Teachable. Managed via a Turborepo monorepo with SvelteKit, Hono Node.js API, PostgreSQL (Drizzle ORM), and Redis caching.
  - **Infrastructure Burden:** Running this application requires provisioning multiple concurrent services (PostgreSQL, Redis, SvelteKit SSR server, Node API).
  - **License:** AGPL-3.0.
- **Verdict:** **REJECTED.** Directly violates the user guideline: *"We DO NOT need a massive production-grade LMS or a huge enterprise platform. We need a compact, polished, genuinely functional AI-powered learning WEB APPLICATION."*

---

### 3.4 Candidate 4: OpenTutor (`zijinz456/OpenTutor`)
- **Strengths:** Apache-2.0 license, modern Python FastAPI + Next.js stack, FSRS implementation, and hybrid RAG.
- **Weaknesses:**
  - **UI Complexity:** Built around 12 composable dynamic workspace blocks with heavy Zustand state synchronization, creating high layout overhead and fragile rendering states on mobile devices.
  - **Node.js + Python Decoupling:** Requires running two separate development servers (Next.js SSR frontend and FastAPI backend), complicating single-click Windows demonstrations.
- **Verdict:** **VIABLE BUT INFERIOR TO QUICKLEARN.** High operational complexity for a college demonstration.

---

### 3.5 Selected Foundation: QuickLearn (`artbyjazi/quicklearn`)
- **Why QuickLearn Wins:**
  1. **Compact & Self-Contained:** Unifies a high-performance FastAPI backend with an embedded React 18 / TypeScript SPA. A single Uvicorn process serves both the REST API and the compiled frontend bundle on `http://127.0.0.1:8080`.
  2. **Zero Heavy Infrastructure:** Relies on embedded SQLite (with WAL journaling) and local ChromaDB. No Docker, no Redis, no PostgreSQL daemons required.
  3. **Verified Learning Workflows:** Out-of-the-box support for PDF parsing, text segmentation, Chroma embedding, FSRS-6 spaced repetition, multi-format quizzes, and evidence-grounded chat.
  4. **Permissive MIT License:** Allows clean adaptation, customization, and branding while maintaining full upstream attribution.
  5. **Proven Stability:** 105 backend unit and integration tests passing with 0 failures on Windows 11.
- **Customization Strategy for EduVerse AI:**
  - Implement full **Student Authentication** (User model, PBKDF2 password hashing, JWT bearer tokens, and user-isolated records).
  - Implement **Knowledge Gap Detection** (algorithmic weak-topic tracking based on actual quiz error history).
  - Implement **Adaptive Revision Planner** (recommendation engine generating prioritized study sessions from FSRS card stability and quiz weakness metrics).
  - Implement **Student Dashboard & Analytics** (real metrics computed from persisted SQLite records: course progress, quiz accuracy, revision queue).
  - Retain the distinctive, polished **EduVerse AI Astra Theme** (deep obsidian `#0B0F17`, celestial violet `#7C3AED`, and vibrant cyan `#06B6D4`).

---

## 4. Conclusion & Next Steps

The **QuickLearn** foundation is formally selected as the architectural base for `EduVerse_Web_Demo`. We proceed directly to implementing the new authentication, knowledge gap, and revision planning modules in `S:\SY\SEM 3\MP\EduVerse_Web_Demo`.
