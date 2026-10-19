# EduVerse AI — An Animated Virtual Tutor for Personalized Learning

[![License: MIT](https://img.shields.io/badge/License-MIT-teal.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-0A2540.svg)](https://python.org)
[![FastAPI: 0.135+](https://img.shields.io/badge/FastAPI-0.135+-005F73.svg)](https://fastapi.tiangolo.com)
[![PyMuPDF: 1.28+](https://img.shields.io/badge/PyMuPDF-1.28+-0A9396.svg)](https://pymupdf.readthedocs.io/)
[![Three.js: WebGL](https://img.shields.io/badge/Three.js-3D%20Avatar-0A192F.svg)](https://threejs.org)
[![Report: 25 Pages](https://img.shields.io/badge/Report-25%20Pages%20Verified-success.svg)](EduVerse_AI_Project_Report/EduVerse_AI_Project_Report.pdf)
[![Tests: 13 Passed](https://img.shields.io/badge/Tests-13%2F13%20Passed-brightgreen.svg)](tests/)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Sufiyan367/EduVerse-AI)

> **Department:** Artificial Intelligence & Data Science  
> **Institution:** Indira College of Engineering and Management (ICEM), Parandwadi, Pune  
> **Affiliation:** Autonomous Institute Affiliated to Savitribai Phule Pune University (SPPU)  
> **Academic Year:** 2026–2027  
> **Project Team:** Aryan Shinde (AI-01), Huzaifa Sheikh (AI-02), Sufiyan Surve (AI-03)  
> **Mentor:** Prof. Monika Patil, Assistant Professor, Department of AI & DS, ICEM Pune

---

## 1. Project Purpose & Overview

**EduVerse AI** is an AI-powered interactive virtual tutor platform engineered to bridge static learning material (lecture slides, textbook chapters, syllabus notes) with active, conversational comprehension. Rather than querying generic search engines or unconstrained public chatbots that risk syllabus mismatch and hallucination, EduVerse AI anchors all interactions strictly in student-uploaded study documents.

---

## 2. Problem Statement

Undergraduate engineering students encounter three critical bottlenecks during digital self-study:
1. **Information Fragmentation:** Course concepts are scattered across dense PDF documents, requiring tedious cross-referencing.
2. **Absence of Contextual Doubt Resolution:** Static documents cannot be interrogated interactively. Querying public search engines frequently yields non-syllabus-aligned derivations.
3. **Lack of Immediate Self-Assessment:** Formative self-testing requires time-consuming manual question extraction.

EduVerse AI resolves this via a closed-loop workflow:
$$\text{Study Material (PDF)} \longrightarrow \text{Text Extraction (PyMuPDF)} \longrightarrow \text{Contextual Q\&A} \longrightarrow \text{Active Recall Quiz} \longrightarrow \text{Immediate Evaluation}$$

---

## 3. Verified Feature Implementation Status

The table below reflects actual empirical test results across all development milestones:

| Feature Dimension | Status | Verification Evidence / Method |
|---|---|---|
| **Application Foundation (FastAPI)** | **Verified** | Live server startup tested; `/api/health` and `/` return HTTP 200 OK |
| **PDF Extraction Engine** | **Verified** | PyMuPDF pipeline tested; multi-page extraction and Unicode whitespace normalization verified |
| **PDF Validation & Error Catching** | **Verified** | 0-byte PDFs, non-PDF streams, corrupt headers, and >25MB size limits safely caught (TC-01, TC-02, TC-03) |
| **Document-Grounded AI Tutor** | **Verified** | Strict context bounding tested; answers cite uploaded syllabus text with clear student disclaimers (TC-04) |
| **Non-Contextual Refusal Handling** | **Verified** | Tested with out-of-scope queries (e.g. quantum gravity); model explicitly states topic is absent from notes (TC-05) |
| **Concept Simplification & Analogy** | **Verified** | Structured analogy breakdown, syllabus definitions, and key takeaway bullet points generated (TC-06) |
| **Automated Quiz Generation** | **Verified** | Generates 3-to-5 MCQs with 4 distinct options, valid 0-indexed answers, and educational rationales |
| **Interactive Quiz Scoring & Evaluation** | **Verified** | Instant client and backend evaluation, percentage computation, passed flag, and answer rationale reveal (TC-07) |
| **Three.js 3D Virtual Tutor Avatar** | **Verified** | WebGL 3D avatar rendered in UI with real-time reactive states (Idle: Teal aura, Thinking: Amber pulse, Explaining: Emerald waves) |
| **LaTeX Academic Report** | **Verified** | Compiled via bundled Tectonic compiler; verified strictly 25 pages without overflow |

---

## 4. System Architecture

EduVerse AI follows a decoupled, 5-tier architecture:

```
[ Student Web Browser ] (React / HTML5 / CSS3 / Three.js WebGL 3D Avatar)
            |
            | RESTful HTTP JSON / Multipart Form-Data
            v
[ API Gateway / Orchestration Tier ] (FastAPI + Pydantic v2 + Uvicorn)
      |                         |                        |
      v                         v                        v
[ Document Parser ]     [ In-Memory Store ]     [ LLM Orchestrator ]
  (PyMuPDF C++ Engine)   (Session & Quiz Store)   (Gemini / OpenAI / OpenRouter / Fallback)
```

1. **Client Tier:** 3-column workspace with drag-and-drop PDF upload, conversational chat stream, prompt recommendation chips, and interactive 3D WebGL avatar.
2. **API Gateway:** FastAPI asynchronous routing with strict Pydantic v2 schema validation and CORS security headers.
3. **Document Ingestion Subsystem:** PyMuPDF (`fitz`) parsing binary PDF streams into cleaned, structured text chunks in under 1.5 seconds.
4. **AI Reasoning Tier:** Pluggable LLM client supporting Google Gemini (`gemini-1.5-flash`), OpenAI (`gpt-4o-mini`), OpenRouter, and a deterministic fallback engine for offline testing.
5. **Assessment Subsystem:** Automated Multiple-Choice Question (MCQ) synthesis and instantaneous score calculation.

---

## 5. Prerequisites & Installation

### Prerequisites
- Python 3.11+
- Git 2.40+
- Modern Web Browser with WebGL enabled (Chrome, Edge, Firefox, Safari)

### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Sufiyan367/EduVerse-AI.git
   cd EduVerse-AI
   ```

2. **Configure Environment Variables:**
   ```bash
   copy .env.example .env
   ```
   Edit `.env` to supply your desired LLM credentials:
   ```ini
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

3. **Install Dependencies:**
   ```bash
   pip install fastapi uvicorn pymupdf pydantic pydantic-settings python-dotenv google-genai requests pytest python-multipart
   ```

---

## 6. How to Run the Application

### Start the Backend and Web Interface
```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Once started:
- **Web Application Workspace:** Open your browser to `http://127.0.0.1:8000/`
- **Interactive OpenAPI Documentation:** Available at `http://127.0.0.1:8000/docs`
- **System Health Diagnostics:** Available at `http://127.0.0.1:8000/api/health`

---

## 7. Cloud Deployment on Render

EduVerse AI is production-ready for deployment on [Render](https://render.com) using the included `render.yaml` Blueprint or as a standard Python Web Service:

### Render Configuration Details:
- **Environment:** Python 3.11+
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- **Environment Variables (Render Dashboard):**
  - `LLM_PROVIDER`: `gemini` (or `openai`, `openrouter`)
  - `GEMINI_API_KEY`: Server-side secret key (never committed to repository)
  - `ENVIRONMENT`: `production`

### Blueprint Deployment:
1. Log in to [Render Dashboard](https://dashboard.render.com).
2. Click **New +** $\to$ **Blueprint**.
3. Connect your repository `Sufiyan367/EduVerse-AI`.
4. Render will parse `render.yaml` automatically and prompt for your secret `GEMINI_API_KEY`.
5. Click **Apply** to deploy the live web service.

---

## 8. How to Use the Application

1. **Study Document Loading:**
   - Click the upload card in the left column or drag and drop an academic PDF file (up to 25 MB).
   - Alternatively, click **"Load Machine Learning Sample Notes"** for an immediate, zero-setup demonstration using verified course material.
2. **Contextual Doubt Resolution:**
   - Type a question in the center conversation box (e.g., *"What is the loss function used in logistic regression?"*).
   - Click **Ask** to receive an explanation grounded strictly in the syllabus text, accompanied by an excerpt citation.
3. **Concept Simplification:**
   - Enter a complex technical term (e.g., *"Overfitting"* or *"Gradient Descent"*).
   - Click **Simplify** to generate a real-world analogy and key bullet points.
4. **Active Recall Quiz:**
   - Select the number of questions (3, 4, or 5) in the right column and click **Generate Quiz**.
   - Select your answers for each question card.
   - Click **Submit & Check Answers** to receive your percentage score, pass/fail status, and detailed question-by-question rationales.
5. **Interactive 3D Virtual Tutor:**
   - The top-right WebGL viewport renders the 3D cybernetic avatar that dynamically transitions between `Idle` (soft teal aura), `Thinking` (pulsing amber halo), and `Explaining` (radiant emerald waves).

---

## 9. Automated Testing & Verification

Run the complete automated test suite with pytest:

```powershell
python -m pytest tests -v
```

### Verified Test Results Summary
```text
tests/test_api_endpoints.py::test_health_endpoint PASSED                 [  7%]
tests/test_api_endpoints.py::test_frontend_root_served PASSED            [ 15%]
tests/test_api_endpoints.py::test_document_upload_and_extraction PASSED  [ 23%]
tests/test_api_endpoints.py::test_invalid_file_extension_rejected PASSED [ 30%]
tests/test_api_endpoints.py::test_sample_document_loader PASSED          [ 38%]
tests/test_api_endpoints.py::test_tutor_query_grounded_workflow PASSED   [ 46%]
tests/test_api_endpoints.py::test_tutor_query_non_contextual_handling PASSED [ 53%]
tests/test_api_endpoints.py::test_concept_simplification_endpoint PASSED [ 61%]
tests/test_api_endpoints.py::test_quiz_generation_and_evaluation PASSED  [ 69%]
tests/test_pdf_service.py::test_valid_pdf_extraction PASSED              [ 76%]
tests/test_pdf_service.py::test_empty_bytes_rejected PASSED              [ 84%]
tests/test_pdf_service.py::test_corrupt_file_rejected PASSED             [ 92%]
tests/test_pdf_service.py::test_size_limit_enforced PASSED               [100%]

============================= 13 passed in 8.68s ==============================
```

---

## 10. Compiling the 25-Page Project Report

The project includes the complete academic LaTeX report conforming strictly to the 25-page format required by the Department of AI & DS at ICEM Pune.

### Compilation using Bundled Tectonic Compiler
```powershell
& "bin\tectonic.exe" "EduVerse_AI_Project_Report\EduVerse_AI_Project_Report.tex"
```

### Page Count Verification Snippet
```powershell
python -c "import pymupdf; doc = pymupdf.open(r'EduVerse_AI_Project_Report\EduVerse_AI_Project_Report.pdf'); print(f'Total Pages: {len(doc)} (Target: 25)')"
```
**Output:** `Total Pages: 25 (Target: 25)`

---

## 11. Known Limitations & Future Scope

### Known Limitations
- Standard text parsing requires machine-readable PDFs; scanned handwritten notes require an external OCR pre-processor.
- Ingestion is currently optimized for single documents up to 25 MB per study session.
- Real-time speech synthesis (TTS lip-sync) is reserved for Phase 2.

### Phased Future Scope
- **Phase 2 (Multimodal Voice):** Speech-to-Text (STT) query input and Text-to-Speech (TTS) natural voice explanations.
- **Phase 3 (Vector RAG):** ChromaDB / FAISS semantic vector indexing for multi-textbook 500+ page curricula.
- **Phase 4 (Analytics):** Student learning curves, historical weak-spot tracking, and adaptive quiz difficulty.
- **Phase 5 (Mobile App):** Cross-platform Flutter client for portable offline study.

---

## 12. Open-Source Licensing & Attribution

- **Project License:** [MIT License](LICENSE) — Copyright (c) 2026 Aryan Shinde, Huzaifa Sheikh, Sufiyan Surve (ICEM Pune).
- **Third-Party Component Notices:** Comprehensive attribution for FastAPI, PyMuPDF, Pydantic, Three.js, and institutional assets is detailed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
