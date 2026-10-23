# EduVerse AI — Local Deployment & Execution Guide

This guide provides exact, verified commands to launch both EduVerse AI applications locally from the consolidated root `EduVerse-AI-Complete`.

---

## Architecture Selection

EduVerse AI maintains two distinct, runnable applications suited for different evaluation contexts:

1. **Baseline Application (`apps/baseline/`):**
   - Pure Python/FastAPI backend with PyMuPDF parser and vanilla JavaScript workstation.
   - Includes interactive Three.js 3D WebGL avatar.
   - Minimal dependency footprint.

2. **Full-Stack Platform (`apps/fullstack/`):**
   - Production-grade desktop learning platform featuring React 18, Vite, and Tailwind CSS.
   - FastAPI backend daemon with SQLite-vec dense memory, FSRS-6 spaced repetition, knowledge gap tracking, adaptive revision planner, and Astra P0 hardened multi-user auth.

---

## 1. Running the Full-Stack Platform (`apps/fullstack/`)

### Prerequisites
- Python 3.11+ (Windows, Linux, or macOS)
- Node.js 18+ (for frontend development/builds; compiled assets are pre-bundled)

### Quick Start (Automated PowerShell Launcher)
```powershell
# Navigate to fullstack app directory
cd apps\fullstack

# Start the full-stack daemon and launch browser
.\run_eduverse.ps1
```
- Gateway URL: **`http://127.0.0.1:8080`**
- One-click demo student login: `student@eduverse.ai` (Password: `demo123`).

### Graceful Shutdown
```powershell
.\stop_eduverse.ps1
```

### Manual Backend Launch (Without Scripts)
```powershell
cd apps\fullstack\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
python -m quicklearn --port 8080 --host 127.0.0.1 --data-dir ..\data
```

---

## 2. Running the Baseline Application (`apps/baseline/`)

### Quick Start
```powershell
# Navigate to baseline app directory
cd apps\baseline

# Install dependencies
pip install -r requirements.txt

# Start with Uvicorn
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
- Open **`http://127.0.0.1:8000`** in your browser.
- Interactive OpenAPI documentation: **`http://127.0.0.1:8000/docs`**.

---

## 3. Configuration & Safe Environment Variables

Copy the safe `.env.example` template to `.env` in the target application directory:
```powershell
cp .env.example .env
```

Ensure real API keys (e.g. `GEMINI_API_KEY` or `OPENROUTER_API_KEY`) and JWT secrets are kept exclusively in local `.env` files and **never committed to Git**.
