# Contributing to EduVerse AI

Thank you for your interest in contributing to **EduVerse AI**! This project is an AI-powered personalized learning platform engineered for engineering students to turn course notes into active comprehension.

---

## 1. Code of Conduct & Academic Integrity

- Be respectful, constructive, and collaborative.
- Maintain academic honesty: ensure code, citations, and benchmarks are truthful and verifiable.
- Never commit private university data, proprietary examination materials, or unredacted personal information.

---

## 2. Development Setup

### Prerequisites
- **Python:** 3.11+
- **Git:** 2.40+
- **Virtual Environment Tool:** `venv`

### Initial Workspace Setup
```powershell
# 1. Clone the repository
git clone https://github.com/Sufiyan367/EduVerse-AI.git
cd EduVerse-AI

# 2. Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # On Windows
# source .venv/bin/activate    # On Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt
```

### Environment Configuration
Copy the example environment template:
```powershell
copy .env.example .env
```
Configure your desired LLM credentials in `.env`:
```ini
LLM_PROVIDER=gemini       # or openai, openrouter, mock
GEMINI_API_KEY=your_key   # required only if using live cloud inference
```
> **Security Rule:** Never commit your `.env` file or any live API keys. `.env` is strictly ignored by `.gitignore`.

---

## 3. Running the Application Locally

Start the development server with hot-reload enabled:
```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Access points:
- **Application UI:** `http://127.0.0.1:8000/`
- **Interactive OpenAPI Docs:** `http://127.0.0.1:8000/docs`
- **System Health Endpoint:** `http://127.0.0.1:8000/api/health`

---

## 4. Running Automated Tests

Before submitting any code changes, always execute the full test suite:

```powershell
python -m pytest tests -v
```

All 17 local offline tests should pass. (The live Render deployment test `test_live_render.py` is safely skipped unless `RUN_LIVE_RENDER_TESTS=1` is explicitly set).

---

## 5. Development Guidelines & Standards

1. **Strict Type Annotations & Schemas:**
   - Use standard Python type hints (`int`, `str`, `list[str]`, `dict[str, Any]`).
   - All API inputs and outputs must be validated using Pydantic v2 schemas in `backend/schemas.py`.

2. **Grounded AI Principles:**
   - AI responses must cite uploaded document excerpts using bracketed citations (`[1]`, `[2]`).
   - If a student query falls outside the uploaded document scope, the tutor must refuse politely rather than hallucinating.

3. **No Phantom Functionality:**
   - Do not add mock responses presented as real AI.
   - Maintain clear separation between live provider inference and deterministic test mocks.

---

## 6. Submitting a Pull Request

1. **Create a topic branch:**
   ```powershell
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```
2. **Make focused, atomic commits:**
   ```powershell
   git commit -m "feat(tutor): add multi-paragraph excerpt citation mapping"
   ```
3. **Verify Git cleanliness:**
   - Run `git status` to ensure no database files (`*.db`), caches (`.pytest_cache/`), or secret files (`.env`) are staged.
4. **Push and open PR:**
   - Push to your fork and submit a PR against `main`. Fill out the [Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md).

---

## 7. Security & Vulnerability Reporting

If you discover a security vulnerability or credential leak, please **do not** open a public GitHub issue. Email the project maintainers directly or reach out through institutional channels at ICEM Pune.
