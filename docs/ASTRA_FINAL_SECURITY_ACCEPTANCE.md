# Independent final security and release acceptance

Date: 24 October 2026 (Asia/Calcutta). **Verdict: FAIL.**

Final release-state check: local and remote feature-branch tip advanced again to **`38044eb48f3b7d383c278dd97b5532b1ec7d8202`** (`polish/github-readiness`). This adds baseline pytest discovery configuration and CI `PYTHONPATH`; `git diff 9e904af HEAD -- EduVerse-AI-Complete/apps/fullstack` is empty. Thus the fullstack findings and tests still apply to its unchanged source. Its [CI run also failed](https://github.com/Sufiyan367/EduVerse-AI/actions/runs/40007649545). Baseline results below predate the new discovery-only configuration; they are not represented as a fresh execution of that latest commit. No fixes from either concurrent commit were authored by this auditor.

Application readiness: blocked by reproduced authorization and assessment-integrity defects. GitHub publication: source and static showcase are published, but release completion is blocked by failed CI, packaging defects and unresolved security findings. Passing supplied tests does not override the independent failures below.

This audit made no application fixes, commits, pushes, merges, deployments, repository-setting changes or production-infrastructure changes. Existing academic assets and student data were preserved. Findings are guidance for the implementing agent; they are not claims of completed remediation.

## 1. Exact release identity and provenance

| Target | Independently observed state |
|---|---|
| Primary repository | `S:\SY\SEM 3\MP`, branch `polish/github-readiness`, origin `https://github.com/Sufiyan367/EduVerse-AI.git` |
| Initial local commit | `9e904afd5fe649c13ad5eb95340772002f8361cd` |
| Published main | `a3744516cf617ff7749aeb5c983c27229fa71e04`, merge of PR #1 |
| Tree equality | Both preceding commits have tree `5bb93f86e299882187fd49a5cae1329d677b95f6`; their tracked contents match even though commit SHAs differ |
| Concurrent update | Another actor committed `05894bef75b0b42f26ac50cb5cdc64c444d27724` during this audit. GitHub branch API confirms this is also the feature-branch tip. Main still returned `a3744516...` at final lookup |
| Scope of concurrent update | Only root/consolidated requirements and root/consolidated standalone browser-test import guards changed. No extended security implementation changed |
| Consolidated directory | `EduVerse-AI-Complete` is a tracked directory in the primary repository, not a separate checkout. Its fullstack Python package and frontend `src` compare byte-for-byte with the extended application (zero differences) |
| Extended checkout | `EduVerse_Web_Demo`, branch `main`, commit `547e82bf902e09b385332d68486b0dd84b4588a1`. Its origin remains `https://github.com/artbyjazi/quicklearn`; do not push there as an EduVerse release destination |
| Working tree | Primary tree was clean after the concurrent CI commit and before these audit documents. Extended checkout had a modified README and untracked reports/launcher backup. No claim that those files are remotely published |

The security probes import `EduVerse-AI-Complete/apps/fullstack/backend` explicitly. They use fresh temporary databases and mock providers. They do not probe real student records or external infrastructure. A SHA-256 manifest of the inspected Python package is retained with the evidence. The published tree contains these same security implementations; this is no longer merely a snapshot-only finding.

## 2. Actual commands and results

Evidence directory on this machine:
`C:\Users\sufiy\.codex\visualizations\2026\10\22\01a1642f-ad56-77b2-89e2-fce9160e260c\final-verification`.

`WEBPY` below means `S:\SY\SEM 3\MP\EduVerse_Web_Demo\backend\.venv\Scripts\python.exe`; it supplies the installed dependencies, not an alternate source snapshot.

| Directory / command | Actual result | Evidence / limitation |
|---|---|---|
| Extended backend: `.venv\Scripts\python.exe -m pytest tests/test_remediation_suite.py -q -p no:cacheprovider` | 8 passed, 1 warning, 10.65s | `remediation.log` |
| Extended backend: `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` | 123 passed, 1 warning, 120.60s | `backend-full.log`; earlier in this verification, before consolidation, not a new clean-install test |
| Extended backend: `.venv\Scripts\python.exe -m pytest tests/test_remediation_suite.py tests/test_user_isolation.py -q -p no:cacheprovider` | 11 passed, 1 warning, 15.05s | Current checkout rerun; passing assertions are narrow |
| Extended frontend: `npm.cmd run typecheck`, `npm.cmd run build` | Both completed successfully | `typecheck.log`, `build.log`; build 69s; uses existing installed dependencies |
| Extended backend: `.venv\Scripts\python.exe tests/verify_full_demo_workflow.py` | Exit 0; script prints 13 steps passed | `workflow.log`; limitations below |
| Consolidated `apps/fullstack`: `WEBPY -m pytest tests -q -p no:cacheprovider` | **74 failed, 49 passed**, 1 warning, 58.16s | `consolidated-full.log`; `pytest.ini` uses strict async mode while many async tests are unmarked |
| Same directory, adding `-o asyncio_mode=auto` | **123 passed**, 1 warning, 128.28s | `consolidated-auto.log`; explicit diagnostic override, not the documented default command |
| Primary root: `WEBPY -m pytest <evidence>\test_independent_release.py -q -p no:cacheprovider --tb=short` | **8 failed**, 1 warning, 16.74s | `independent-release-final.log`; all are failed security/integrity assertions, not fixture/import failures |
| Consolidated frontend: `npm.cmd run typecheck`, `npm.cmd run build` | Both exit 1: `tsc` not recognized | `release-typecheck.log`, `release-build.log`; dependencies absent in that directory |
| Consolidated frontend: `node scripts/copy-static.mjs` | Exit 1: `MODULE_NOT_FOUND` | The referenced build script is absent, independently of dependency installation |
| Isolated baseline copy: `$env:LLM_PROVIDER='mock'; python -m pytest tests -q -p no:cacheprovider` | **16 passed, 1 failed, 1 skipped**, 9.28s | `baseline.log`; history ordering test failed; live Render test skipped |

Baseline code/frontend/tests were copied to `baseline-snapshot` under the evidence directory because baseline storage hardcodes its local `data` directory. Existing data and `.env` were not copied. The baseline test output may show original source paths from copied bytecode; execution was from the isolated copy. Baseline health, frontend serving, sample PDF upload, invalid/corrupt PDF and size checks ran through TestClient. This is not proof of a cold-started externally served baseline or real AI inference.

The 13-step script uploads **TXT**, reports the source still **pending**, creates a chat without asking a question, inserts a quiz item/attempt/note directly into SQLite, then disposes and reinitializes the engine in the same process. Its successful output proves those assertions only. It does not establish completed PDF ingestion, real quiz generation/grading, a grounded provider response, browser behavior or operating-system process restart durability. Its token output is only a fixed header prefix, not a complete credential; do not expand logging to real tokens.

The TestClient runs report a Starlette/httpx deprecation warning. No tests were deleted, rewritten to pass, or weakened by this audit.

## 3. Findings and exact remediation guidance

Paths in this section are relative to `EduVerse-AI-Complete/apps/fullstack/backend/quicklearn`, unless otherwise stated. Status of every finding is **open**; no targeted application remediation was performed.

### F01 — High: incomplete object authorization

Affected: `api/cards.py:get_due` (line 59), `api/chat.py:create_chat/get_messages/delete_chat/resolve_citations/chat_socket` (64 onward), `api/quiz.py:submit_answer` (187). Additional unscoped routes were found by inspection in library, jobs, knowledge-gap and quiz reset/list APIs.

Reproduction: seed Alice's private source/card/session and Bob. Bob GETs `/api/v1/cards/due?source_id=<Alice source>` and receives HTTP 200 with Alice's card front/back. Create Alice's chat; anonymous GET `/api/v1/chat/<id>/messages` returns its metadata. Anonymous POST to Alice's quiz answer endpoint succeeds, score 1.0 and mastery 0.3. These three independent HTTP probes fail their required denial assertions.

Root cause: selective route-level checks were added, but other routes retain global queries and have no authenticated ownership dependency. Chat/session records lack comprehensive user scoping; the router itself supplies no global guard. Impact: unauthorized reads and changes to another student's learning state. Chat deletion is also unguarded in code; the probe did not execute deletion.

Minimal fix: require authenticated user on every private route and WebSocket; scope object lookup, retrieval, mutations and aggregate queries to that user. Add ownership to chats/sessions where needed. Explicitly define a read-only public corpus policy rather than treating null ownership as universally writable. Audit jobs, search, citations, exports, folders, podcasts and mastery reset too.

Regression: Alice/Bob/anonymous/invalid-token matrix for read/create/update/delete, including guessed IDs, parent scope, WebSocket and indirect citation/search access. Private resources must not appear in due queues or aggregates.

### F02 — High: ordinary students can change global provider settings

Affected: `api/system.py:patch_settings` (122), `api/auth.py:register`.

Reproduction: Bob PATCHes `/api/v1/settings` with a changed `routing.standard`; HTTP 200. The test changes only a mock provider in a temporary database. Root cause: any authenticated account satisfies the only check, while settings are installation-wide. Impact: one student can alter other users' provider routing and availability. Exfiltration through a malicious provider URL was not exercised and is not claimed as a demonstrated exploit.

Minimal fix: installation-admin capability for global settings and provider diagnostics, or genuinely per-user settings. Validate configurable destinations and prevent diagnostics from forwarding stored credentials to an arbitrary caller-selected endpoint. Test that self-registration conveys no administrative privileges and Bob cannot alter Alice/global routing.

### F03 — High: concurrent quiz replay still inflates mastery

Affected: `api/quiz.py:submit_answer` (187); `db/models.py:QuizAttempt`.

Reproduction: a barrier-controlled mock grader lets two concurrent `submit_answer` calls pass the existing-attempt check before either writes. Actual result: **2 attempts, mastery 0.51** for one correct question. This is an in-process deterministic concurrency reproduction of the route handler, not a remote load attack.

Root cause: check-before-await-before-insert, no unique session/question constraint, and mastery update performed for each inserted attempt. Sequential replay tests pass but do not cover this race.

Minimal fix: database uniqueness for the intended attempt identity, transactional insertion/claim and mastery update only for the winning insert; explicitly resolve preexisting duplicates before migration. Preserve idempotent response behavior for losers. Also handle session closure during grading. Regression: concurrent HTTP submissions, retries, session-close race, one attempt and one mastery delta.

### F04 — High: provider outage is still counted as a wrong answer

Affected: `api/quiz.py:submit_answer` ungraded branch and `session_results` (329); `pipeline/generate/quiz.py:grade_answer`; `db/models.py:QuizAttempt`.

Reproduction: mock grading timeout returns `is_graded=false`, but persists `score=0`, `is_correct=false`. Retrying returns `duplicate=true`; results report `answered=1` and zero score. The schema does not persist an ungraded state, so result consumers cannot distinguish an outage from incorrect knowledge.

Root cause: mastery protection was implemented without assessment-status persistence or retry semantics. Impact: inaccurate assessment evidence and an unrecoverable failed grade within that session, even though immediate mastery is preserved.

Minimal fix: explicit pending/ungraded/graded/failed status, nullable score until graded, exclusion from scores/gaps/mastery, retry transition that grades once. Migrate historical outage attempts deliberately. Regression: timeout/429, restart, recovery/retry, aggregates and gap recommendations, without penalty or duplicate learning updates.

### F05 — Medium: flashcard undo erases subsequent learning

Affected: `study/review.py:undo_review`.

Reproduction: Good review raises mastery to 0.3; later correct quiz raises it to 0.51; undo of the earlier card review restores mastery to 0.0. The isolated last-action undo regression passes, but this interleaved case fails.

Root cause: restoring an old shared-concept snapshot overwrites newer events. Minimal fix: ordered learning events with recomputation, or reject stale undo with an explicit conflict rather than overwriting newer evidence. Restore only valid scheduler state atomically. Regression: two cards sharing a concept, intervening quiz, repeated undo, concurrent review and restart.

### F06 — Medium: citation validation still permits unsupported assertions

Affected: `api/chat.py:validate_answer` (173).

Reproduction: provide excerpt `Water freezes at zero degrees Celsius.` and candidate `The Moon is made of green cheese.` with no citation. The validator returns the unsupported sentence unchanged with empty citations. Fabricated-only citation and no-context tests pass. A valid ID is also not proof that its passage entails a claim; semantic correctness was not established.

Minimal fix: abstain for uncited substantive answers, validate per-claim evidence, reject unsupported portions instead of merely stripping markers, and present uncertainty honestly. Regression: uncited, mixed valid/invalid, irrelevant valid citation, fabricated citation and malicious instructions in source material. Do not promise guaranteed grounding from ID validation alone.

### F07 — High (release blocker): consolidated package is not reproducibly buildable as documented

Affected: `apps/fullstack/pytest.ini`, `frontend/package.json`, missing `frontend/scripts/copy-static.mjs`; consolidated README setup and launch scripts.

Evidence: default suite gives 74 failures; async override gives 123 passes. Frontend dependencies are absent; even after installing them, the final build step references a file missing from both disk and the tracked release. No frontend lockfile is tracked. Baseline README says run `pip install -r requirements.txt` inside `apps/baseline`, where that file is absent. Fullstack launcher falls back to an absolute developer-machine venv path or system Python and does not provision dependencies. Root CI tests only baseline, not consolidated backend/frontend.

Minimal fix: include build scripts, preserve original test configuration, add a reviewed lockfile, explicit backend/frontend install steps and portable launch paths. From consolidated baseline, use the correct root dependency path or supply a dedicated manifest. Run clean-checkout install/build/API tests in CI for both architectures. Regression: fresh-machine commands exactly as documented, with no sibling checkout or prebuilt assets silently substituting for the build.

### F08 — Medium: baseline history order is nondeterministic

Affected: baseline `backend/services/storage_service.py:save_evaluation/get_assessment_history`.

Evidence: `test_quiz_history_persistence` failed because history[0] referenced an earlier quiz. Evaluations use second-resolution timestamp strings and order only by that value; tests create multiple evaluations within the same second. Minimal fix: higher-resolution chronological ordering plus a deterministic tie-breaker/migration; test two submissions in the same second and ensure the most recent event appears first. This failure is not evidence that persistence itself is absent.

### F09 — Medium: release documentation and upstream attribution need correction

Affected: root/consolidated README, THIRD_PARTY_NOTICES and launcher shutdown claims.

Evidence: README still advertises the removed Three.js avatar, guaranteed strict grounding and static passing-test badges despite failed release checks. Static Pages banner correctly states its limitations, but initial tutor copy still promises strict grounding. `stop_eduverse.ps1` uses `Stop-Process -Force` with broad command/path matching, despite being described as graceful. Neither tracked third-party notice includes the upstream Quicklearn copyright; the original extended checkout's MIT license names **Jad Ghazi (2026)**, whereas only the new project license is tracked in the consolidated release.

Minimal fix: preserve upstream license/attribution with the copied code, accurately document both applications, distinguish sample fixtures from recorded outcomes, and replace static success claims with commit-specific evidence/CI links. Review dependency license obligations separately; this audit does not give a legal compliance conclusion. Make shutdown ownership exact and graceful before claiming restart safety. Regression: documentation/link checks, attribution inventory and a controlled shutdown/restart test with active work.

## 4. Status of the six original categories

| Original category | Independent conclusion |
|---|---|
| Anonymous ownership bypass | Partially fixed for direct sources/notes/cards operations; **still open**, F01/F02 |
| Weak JWT signing/validation | Known default is rejected, random persisted local key and production env requirement are present; HS256/type/expiry/subject checks and supplied regressions pass. Not a blanket security approval |
| Quiz replay | Sequential duplicate/closed/out-of-scope cases pass; **concurrent replay open**, F03 |
| Provider failure penalty | Immediate mastery preserved; **scores/results and retry still wrong**, F04 |
| Review undo | Last isolated review restores; **interleaved learning lost**, F05 |
| Unsupported answers | Empty retrieval and fabricated-only citations abstain; **uncited claims survive**, F06 |

JWT remaining hardening: local file reads accept any sufficiently long persisted value; key creation is not atomic; storage failure returns a new ephemeral value on each call rather than a stable cached key. Nonfinite numeric expiry and malformed Authorization schemes need explicit tests. These are inspected edge cases, not demonstrated remote token-forgery exploits. Authentication routes have no evident request throttling; brute-force/resource-exhaustion testing was not performed.

## 5. Additional security coverage and limits

- SQL: inspected ORM predicates and baseline bound-parameter queries; no concrete SQL injection demonstrated. This is not an exhaustive query audit.
- Uploads: baseline synthetic valid, corrupt, extension and size cases ran. Extended single-request upload streams with a 2 GiB cap and sanitizes filename/path components. Resumable initialization still allows anonymous ownership, and chunk body is buffered before application validation. Authentication, quotas and parser resource limits need broader tests; no large-file or destructive payload was sent.
- XSS: React chat avoids raw HTML; search snippets have a sanitizer and Mermaid uses strict mode. These controls were inspected, not exhaustively bypass-tested. No XSS exploit claimed.
- CORS/errors: extended development CORS limits origins to localhost Vite ports; baseline configuration includes wildcard origin. Public-host hardening is not verified. Provider exceptions are interpolated into feedback/logs; review redaction before exposing upstream errors. No actual secret leakage from those errors was demonstrated.
- Database: temporary migration/fixture tests and same-process reopen workflow ran. Concurrency defects are proven above. Real process crash recovery, restart persistence and migration of an existing multi-user corpus remain unverified.
- Secrets: scanned all locally reachable Git revisions using filename-only matches for Google key, GitHub PAT, long `sk-` and private-key markers: zero matches. Remote tree listing (790 entries, not truncated) had no paths ending `.env`, `.jwt_secret`, `.sqlite`, `.db` or `.log`. This limited pattern/path check does not prove all credentials or personal data are absent; binary/academic contents and all token formats were not exhaustively inspected.
- Dependencies: inspected manifests and lack of a tracked frontend lockfile. No current advisory-database scan completed; vulnerability status is **unverified**, not clean.
- Academic material: 178 tracked paths matched the academic/PDF/PPTX/TeX inventory query; this audit did not modify them. Their content and licensing were not revalidated.

## 6. Actual service and GitHub verification

`Invoke-WebRequest http://127.0.0.1:8080/api/v1/health -TimeoutSec 10` failed with connection refused. Therefore current live login, completed PDF ingestion, real-provider grounded answers, quiz/card browser actions and restart persistence were **not verified**. Historical backend log inspected: successful startup/worker registration and one jobs WebSocket connection; it cannot prove current uptime or clean live workflows. No running service or existing database was restarted or changed.

An earlier HTTP attempt was blocked by the automatic approval reviewer's usage limit, not an unsafe-action finding. A later read-only HTTP check was approved and ran. Browser-tool initialization also failed (missing kernel-assets path); fallback isolated Edge/Playwright loaded Pages successfully.

Pages HTTP check: **200**, 11,928 bytes. Browser title: `EduVerse AI — Evidence-First Academic Workspace`. Visible preview banner says live AI, PDF ingestion and user persistence require a local backend. Static fixture concepts render. Browser console captured **one 404 resource error** with no corresponding URL in the captured response list; no JavaScript page exception was reported. This is not a claim of a clean console or all interactive paths tested. Evidence: `pages-browser.log`, `pages.png`, runner `pages-browser.cjs`.

Remote [Pages workflow](https://github.com/Sufiyan367/EduVerse-AI/actions/runs/40005759002) succeeded for `a3744516...`; upload scope is `deployments/github-pages`, not the entire repository. Its assets and workflow are present remotely. The page is a static preview, not a hosted authenticated AI backend.

Remote [main CI](https://github.com/Sufiyan367/EduVerse-AI/actions/runs/40005759005) failed at pytest. The subsequently pushed [feature-branch CI](https://github.com/Sufiyan367/EduVerse-AI/actions/runs/40006832744) also failed at lookup. Exact remote failure cause was not inferred from local failures without logs. The prior Render URL was inaccessible through the web tool; its current health/deployment claim remains unverified.

## 7. Required acceptance gates

1. Fix F01–F04 and F07; add the independent regressions to maintained tests and prove they pass without weakening assertions. Resolve stale undo and grounding behavior before presenting those capabilities as reliable.
2. Freeze a reviewed commit and run both architectures from a clean checkout. Default test commands, frontend build and GitHub CI must pass on that exact commit.
3. Start the chosen demo on loopback using synthetic accounts and PDF. Verify login, ready ingestion/segments, cited real-provider answer, unsupported-question abstention, quiz, cards, isolation and absence of student penalty on provider failure.
4. Prove graceful process restart with retained accounts/sources/assessments and unchanged ownership, using backed-up test data. Inspect console/server logs for that run.
5. Keep Pages visibly marked static; correct README setup/claims/attribution and verify links. Recheck source, workflows, deployment SHA and limited secret checks after the final commit.

These gates remain open. Publishing source and a functioning static preview does not establish application readiness or full GitHub release acceptance.
