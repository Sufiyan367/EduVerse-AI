# EduVerse AI — Setup & College Demo Guide

**Project:** EduVerse AI — AI-Powered Personalized Learning Platform  
**Target:** College Mini-Project Demonstration & Evaluation  
**Author:** Senior Full-Stack & AI Application Engineer  
**Date:** October 23, 2026  
**Status:** Ready for Live Evaluation  

---

## 1. Quick Start: 1-Minute Windows 11 Launch

EduVerse AI is fully self-contained on Windows 11. No Docker, no Kubernetes, and no complex external databases are required.

### Option A: Double-Click Batch Launch (Recommended for Demo)
1. Open Windows File Explorer to:
   ```text
   S:\SY\SEM 3\MP\EduVerse_Web_Demo
   ```
2. Double-click `run_eduverse.bat`.
3. The script verifies the Python virtual environment, executes database migrations, launches the FastAPI server on `http://127.0.0.1:8080`, and opens your default web browser automatically.

### Option B: PowerShell Command Line Launch
Open PowerShell in `S:\SY\SEM 3\MP\EduVerse_Web_Demo` and run:
```powershell
.\run_eduverse.ps1
```
*(To stop the server safely without leaving background processes, run `.\stop_eduverse.bat` or `.\stop_eduverse.ps1`)*

### Option C: Developer Manual Launch
```powershell
cd "S:\SY\SEM 3\MP\EduVerse_Web_Demo\backend"
.\.venv\Scripts\Activate.ps1
python -m uvicorn quicklearn.main:app --host 127.0.0.1 --port 8080 --reload
```
Then navigate to `http://127.0.0.1:8080` in your web browser.

---

## 2. Demo User Credentials

The SQLite database is pre-seeded with a default demo student account upon startup:

| Field | Value |
|---|---|
| **Email** | `student@eduverse.ai` |
| **Password** | `demo123` |
| **Role** | Demo Student (`EduVerse Scholar`) |

> **Pro-Tip for Live Demos:** On the web application login modal, simply click the purple **"Demo Student"** button. It auto-fills the credentials and logs in immediately! You can also register any new custom student account on the spot.

---

## 3. College Mini-Project Demo Walkthrough (Presentation Script)

Follow this 5-minute structured demonstration script to present EduVerse AI to professors, project guides, and external evaluators.

### Act 1: The Student Dashboard (Personalized Learning Overview)
1. Open `http://127.0.0.1:8080`.
2. Observe the **Live Metrics Header**:
   - Enrolled Documents count
   - Flashcards in memory
   - Spaced Repetition Due Reviews
   - Total Quiz Attempts & Average Quiz Accuracy %
   - FSRS 30-Day Retention Health %
3. Point out the **Chronological Activity Feed** showing recent uploads, quiz attempts, and revision sessions.
4. Highlight that there are zero fake holograms or gimmicks—only clear, high-density educational data.

### Act 2: Document Ingestion into Study Library
1. Click **"Library"** in the top navigation bar.
2. Click **"Upload"** and select a study document (PDF, TXT, DOCX, or Markdown).
3. Explain to the evaluator:
   - *"The backend parses the document using native text extractors, generates contextual semantic chunks, and indexes embeddings into a local ChromaDB vector store."*
4. Notice how the document status transitions from `pending` to ready, and concepts are automatically extracted.

### Act 3: Evidence-Grounded AI Tutoring (RAG with Citations)
1. Click **"Chat"** in the navigation.
2. Select your uploaded document as the study scope.
3. Ask a conceptual question based on the document (e.g. *"Explain the time complexity of balanced search trees"*).
4. Point out the **bracketed citation pills (e.g., `[1]`)**:
   - Hover or click the citation to reveal the exact source document chunk.
   - Explain to the evaluator: *"EduVerse AI does not fabricate or hallucinate answers. Every response is strictly grounded in the ingested study material with forensic citations."*

### Act 4: Interactive Quiz & Real Score Persistence
1. Click **"Quiz"** in the navigation.
2. Generate an assessment from the document or select an existing quiz.
3. Answer the multiple-choice questions interactively. Intentionally choose an incorrect answer for at least one question (e.g. selecting `O(n)` instead of `O(log n)`).
4. Submit the quiz and observe immediate grading and pedagogical explanations.
5. Explain to the evaluator: *"Quiz attempts, question IDs, student choices, and correctness are immediately persisted into our ACID-compliant SQLite relational database."*

### Act 5: Algorithmic Knowledge Gap Detection (The Standout Feature!)
1. Click **"Knowledge Gaps"** in the navigation (`/knowledge-gap`).
2. Show the evaluator the **Topic Mastery Breakdown**:
   - Notice that the topic where an error occurred is flagged as **`CRITICAL`** (<60% accuracy).
3. Click the topic card to expand the **Forensic Error Evidence**:
   - The card shows the exact question failed, the user's incorrect answer, and the verified correct answer.
   - Explain to the evaluator: *"Instead of vague feedback, EduVerse AI uses algorithmic weakness tracking to provide students with precise evidence of where their conceptual understanding broke down."*

### Act 6: Adaptive Revision Planner
1. From the Knowledge Gap card, click **"Schedule Revision"** or click **"Revision Planner"** in the navigation (`/revision`).
2. Inspect the **Prioritized Recommendations**:
   - `HIGH Priority`: Critical Knowledge Gaps identified by quiz errors.
   - `MEDIUM Priority`: FSRS Flashcards due for spaced repetition review today.
   - `LOW Priority`: New documents needing initial assessment.
3. Schedule a 25-minute Pomodoro revision session.
4. Mark the session as **"Complete"** when finished and observe the learning progress reflected across the platform.

### Act 7: Application Restart & Database Integrity Verification
1. To prove to evaluators that all data is truly persisted in SQLite (and not merely stored in browser memory):
2. Stop the server (`.\stop_eduverse.bat`) and restart it (`.\run_eduverse.bat`).
3. Refresh the browser and log back in.
4. All uploaded documents, quiz attempt statistics, identified knowledge gaps, and scheduled revision sessions remain 100% intact!

---

## 4. AI Provider Setup & Configuration

EduVerse AI features a pluggable AI provider gateway:

### Option 1: Offline Deterministic Mock (Default / Zero-Config)
No API keys or GPU required. Perfect for continuous integration, rapid testing, and offline lab environments.
Set in `.env`:
```ini
AI_PROVIDER=mock
```

### Option 2: Local LLM via Ollama (Recommended for GPU Demos)
1. Install [Ollama](https://ollama.ai) on Windows.
2. In terminal, pull a model:
   ```powershell
   ollama pull llama3.2
   ```
3. Set in `.env`:
   ```ini
   AI_PROVIDER=ollama
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=llama3.2
   ```

### Option 3: Local LLM via LM Studio
1. Launch LM Studio, load your desired GGUF model, and start the Local Server on port `1234`.
2. Set in `.env`:
   ```ini
   AI_PROVIDER=lmstudio
   LMSTUDIO_BASE_URL=http://localhost:1234/v1
   ```

### Option 4: Cloud API (OpenAI / Google Gemini)
Set your API key in `.env`:
```ini
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
```

---

## 5. Frequently Asked Questions by Project Evaluators

**Q: Is the AI response faked or simulated?**  
**A:** Absolutely not. When configured with Ollama, LM Studio, or OpenAI/Gemini, genuine HTTP network calls are made to the inference endpoints. If a model or server is unavailable, the application transparently raises a descriptive error rather than generating false mock text.

**Q: Where is data stored?**  
**A:** Relational metadata (users, sources, quiz attempts, knowledge gaps, revision sessions, notes) is stored in a clean SQLite database managed via Alembic migrations. Embeddings are stored locally in ChromaDB vector files. Uploaded files reside in the local media directory.

**Q: How does the Knowledge Gap Detector differ from standard quiz scores?**  
**A:** Standard LMSs only show an overall percentage (e.g. "70%"). EduVerse AI's Knowledge Gap Detector performs item-level forensic analysis to group failures by semantic topic, categorize mastery levels (`CRITICAL`, `MODERATE`, `PROFICIENT`, `MASTERED`), capture concrete question evidence, and feed directly into the Adaptive Revision Planner.
