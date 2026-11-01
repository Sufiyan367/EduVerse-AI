# EduVerse AI — Canonical Fullstack Application

**Path:** `EduVerse-AI-Complete/apps/fullstack`  
**Application Type:** FastAPI Backend + React 18 TypeScript Frontend  
**Database:** SQLite (`data/quicklearn.db`) with `sqlite-vec` vector indexing  
**Local Inference Engine:** Ollama with `qwen3.5:4b` reasoning model (NVIDIA RTX 3050 GPU accelerated)  

---

## 1. Architecture Overview

This directory contains the production-grade canonical application for **EduVerse AI**:

- **`backend/quicklearn`**: Core FastAPI application package.
  - `api/`: REST and WebSocket endpoints (`auth.py`, `chat.py`, `sources.py`, `cards.py`, `quiz.py`, `system.py`, `dashboard.py`).
  - `pipeline/`: Ingestion, extraction (`document.py`), and boundary-aware chunking (`segment.py`).
  - `rag/`: Vector storage via `sqlite-vec` (`index.py`), hybrid retrieval with BM25 (`retrieve.py`).
  - `providers/`: Adapters for Local Ollama (Primary), Google Gemini, Groq, OpenAI, Anthropic, and local Mock mode.
- **`frontend/`**: Modern React 18 SPA built with Vite, Tailwind CSS, Lucide Icons, and KaTeX.
- **`data/`**: Runtime directory containing the SQLite database and uploaded document media files (gitignored).
- **`tests/`**: Comprehensive test suites (154 tests) covering live local inference, RAG retrieval, citation verification, auth, and multi-tenant isolation.

---

## 2. Local AI & Reasoning Architecture (Qwen3.5:4b + RTX 3050)

EduVerse AI runs 100% locally with zero external API fees and zero telemetry using Ollama:

- **Model:** `qwen3.5:4b` (3.3 GB parameters, native multimodal reasoning).
- **GPU Acceleration:** Offloaded to NVIDIA GeForce RTX 3050 Laptop GPU (allocated ~3.7 GB / 6.1 GB VRAM).
- **Reasoning Mode:** Native `think="high"` configured via `/api/chat` for multi-step mathematical, algorithmic, and conceptual reasoning.
- **Privacy Filter:** All internal `<think>...</think>` scratchpad tokens are filtered before reaching the frontend or logs.
- **Context Window:** `num_ctx=4096` tokens (expandable to 8192).
- **3-Tier Provider Routing:**
  1. **Tier 1 (Primary):** Local Ollama (`qwen3.5:4b`).
  2. **Tier 2 (Cloud):** External cloud providers (Gemini/Groq/OpenAI) are **blocked** unless `ALLOW_CLOUD_FALLBACK=true` is explicitly set.
  3. **Tier 3 (Local Mock):** If Ollama is offline and cloud fallback is false, EduVerse gracefully operates in deterministic mock mode citing real excerpts without crashing.

---

## 3. Server Health & Reconnection Architecture

The WebSocket and health check layers are completely decoupled from LLM availability:
- **Core Server Health (`/api/v1/health`):** Fast HTTP 200 endpoint indicating server reachability and DB health.
- **Dedicated LLM Health (`/api/v1/health/llm`):** Reports Ollama connection status, active model, reasoning level, GPU model, and VRAM allocation.
- **WebSocket Handshake Fix:** Conforms to RFC 6455 by properly negotiating browser `Sec-WebSocket-Protocol: bearer.<token>` subprotocols, eliminating the persistent `"Reconnecting to EduVerse server…"` UI banner.
- **Status Pills in UI:** Live green/amber/gray indicators in sidebar and chat header displaying model status and reasoning level.

---

## 4. Running Canonical Backend

### Step 1: Ensure Ollama is Running
```powershell
ollama serve
ollama pull qwen3.5:4b
```

### Step 2: Start Backend Server
From Windows Command Prompt:
```cmd
cd /d "S:\SY\SEM 3\MP\EduVerse-AI-repo\EduVerse-AI-Complete\apps\fullstack\backend"
set PYTHONPATH=.
python -m quicklearn --port 8080 --host 127.0.0.1 --data-dir "..\data"
```

Once running, navigate your web browser to: **`http://127.0.0.1:8080`**

---

## 5. Running Automated Tests

### 1. Live Local Inference Test Suite (Ollama + Qwen3.5:4b on GPU)
```cmd
cd /d "S:\SY\SEM 3\MP\EduVerse-AI-repo\EduVerse-AI-Complete\apps\fullstack"
set PYTHONPATH=backend
pytest tests/test_live_ollama_qwen_inference.py -v
```

### 2. Ollama Reasoning & Handshake Suite
```cmd
pytest tests/test_ollama_reasoning_integration.py -v
```

### 3. RAG Pipeline Repair & 15-Category Benchmark Suite
```cmd
pytest tests/test_rag_pipeline_repair.py -v
```

### 4. Full Canonical Regression Suite
```cmd
pytest tests -v --tb=short
```

---

## 6. Building Frontend
```cmd
cd /d "S:\SY\SEM 3\MP\EduVerse-AI-repo\EduVerse-AI-Complete\apps\fullstack\frontend"
npm ci
npm run build
```
Compiled static assets are copied to `backend/quicklearn/static` and served directly by FastAPI.
