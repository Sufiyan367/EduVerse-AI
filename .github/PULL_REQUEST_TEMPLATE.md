## Pull Request Description

### Summary of Changes
<!-- Provide a brief, high-level summary of what this PR introduces or fixes. -->

### Related Issue / Objective
<!-- Link to issue: Fixes #123 or relates to task objective -->

---

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Documentation update (README, reports, diagrams)
- [ ] Test suite enhancement (adding or refining unit/integration tests)
- [ ] Refactoring / Code quality (no functional changes)

---

## Verification & QA Checklist
Before submitting, please ensure the following checks have been completed:

- [ ] **Local Tests:** Ran `python -m pytest tests -v` and all relevant tests passed.
- [ ] **Secret Hygiene:** Verified zero API keys, secrets, or `.env` files are committed.
- [ ] **Data Preservation:** Ensured no SQLite databases, user uploads, or private student documents are tracked.
- [ ] **Academic Deliverables:** Verified LaTeX report and project presentations remain intact.
- [ ] **Documentation:** Updated `README.md` or relevant docs if behavior changed.
- [ ] **Git Cleanliness:** Focused commit history with clear, descriptive commit messages.
