# EduVerse AI — An Animated Virtual Tutor for Personalized Learning

[![License: MIT](https://img.shields.io/badge/License-MIT-teal.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-0A2540.svg)](https://python.org)
[![FastAPI: 0.110+](https://img.shields.io/badge/FastAPI-0.110+-005F73.svg)](https://fastapi.tiangolo.com)
[![PyMuPDF: 1.28+](https://img.shields.io/badge/PyMuPDF-1.28+-0A9396.svg)](https://pymupdf.readthedocs.io/)
[![Report: 25 Pages](https://img.shields.io/badge/Report-25%20Pages%20Verified-success.svg)](EduVerse_AI_Project_Report/EduVerse_AI_Project_Report.pdf)

> **Department:** Artificial Intelligence & Data Science  
> **Institution:** Indira College of Engineering and Management (ICEM), Parandwadi, Pune  
> **Affiliation:** Autonomous Institute Affiliated to Savitribai Phule Pune University (SPPU)  
> **Academic Year:** 2026–2027  
> **Team:** Aryan Shinde (AI-01), Huzaifa Sheikh (AI-02), Sufiyan Surve (AI-03)  
> **Mentor:** Prof. Monika Patil, Assistant Professor, Dept. of AI & DS, ICEM Pune

---

## 1. Project Purpose & Overview

**EduVerse AI** is an AI-powered interactive virtual tutor platform engineered to bridge static learning material (lecture slides, textbook chapters, syllabus notes) with active, conversational comprehension. Rather than querying generic search engines or unconstrained public chatbots that risk syllabus mismatch and hallucination, EduVerse AI anchors all interactions strictly in student-uploaded study documents.

---

## 2. Problem Statement

Undergraduate engineering students encounter three critical bottlenecks during digital self-study:
1. **Information Fragmentation:** Course concepts are scattered across dense PDF documents, requiring tedious cross-referencing.
2. **Absence of Contextual Doubt Resolution:** Static documents cannot be interrogated interactively.
3. **Lack of Immediate Self-Assessment:** Formative self-testing requires time-consuming manual question extraction.

EduVerse AI resolves this via a closed-loop workflow:
$$\text{Study Material (PDF)} \longrightarrow \text{Text Extraction (PyMuPDF)} \longrightarrow \text{Contextual Q\&A} \longrightarrow \text{Active Recall Quiz} \longrightarrow \text{Immediate Evaluation}$$

---

## 3. Current Feature Implementation Status

The table below reflects actual empirical test results across development milestones:

| Feature Dimension | Status | Verification Evidence / Method |
|---|---|---|
| **LaTeX Academic Report** | Verified (Done) | Compiled via bundled Tectonic compiler; verified strictly 25 pages via PyMuPDF |
| **Project Workspace & Baseline** | Verified (Done) | Git initialized, `.gitignore`, `.env.example`, MIT License, `THIRD_PARTY_NOTICES.md` configured |
| **Application Foundation (FastAPI)** | Verified (Done) | Uvicorn server started; `/api/health` and `/` respond with HTTP 200 OK |
| **PDF Upload & Validation (PyMuPDF)** | Verified (Done) | PyMuPDF pipeline tested; size limits, magic bytes, empty/corrupt validation verified |
| **Document-Grounded AI Tutor** | Verified (Done) | LLM orchestrator tested; contextual Q&A, out-of-scope refusal, and concept simplification verified |
| **Automated Quiz Generation** | Verified (Done) | MCQ generator tested; 4-option validation, option index bounding, and rationale verified |
| **Interactive Quiz Scoring** | Verified (Done) | Scoring engine tested; percentage calculation, passed flag, and breakdown verified |
| **3D Avatar & Web Interface UX** | Verified (Done) | 3-column workspace with Three.js WebGL reactive avatar (Idle/Thinking/Explaining) verified |

---

## 4. Technology Stack & Architecture

- **Client Tier:** React.js / Modern Interactive Web UI (HTML5, Tailwind/CSS3, Lucide icons, Three.js WebGL canvas for animated tutor persona).
- **Application & API Gateway:** Python 3.11+ / FastAPI, asynchronous endpoints with Pydantic v2 schemas.
- **Document Processing Engine:** PyMuPDF (`fitz`), C-level high-performance text parsing and sanitization.
- **AI / LLM Intelligence Layer:** Pluggable LLM orchestrator supporting Google Gemini, OpenAI, OpenRouter, and a deterministic offline test provider.
- **Documentation Engine:** Tectonic standalone XeTeX compiler.

---

## 5. Prerequisites & Environment Setup

### Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend development)
- Git 2.40+

### Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Sufiyan367/EduVerse-AI.git
   cd EduVerse-AI
   ```

2. **Configure Environment Variables:**
   ```bash
   copy .env.example .env
   ```
   Add your API key (e.g., `GEMINI_API_KEY` or `OPENAI_API_KEY`) to `.env`.

3. **Install Python Dependencies:**
   ```bash
   pip install fastapi uvicorn pymupdf pydantic python-dotenv google-genai requests pytest
   ```

---

## 6. Running the Application

### Running the Backend Service
```bash
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```
Interactive OpenAPI documentation will be accessible at `http://127.0.0.1:8000/docs`.

### Compiling the 25-Page Project Report
```powershell
& "bin\tectonic.exe" "EduVerse_AI_Project_Report\EduVerse_AI_Project_Report.tex"
```

---

## 7. License & Third-Party Attributions

This project is licensed under the [MIT License](LICENSE). Third-party open-source components, toolkits, and academic assets are attributed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
