# Feynlist — Evals

Statuses: **Executed-Pass**, **Executed-Fail** or **Proposed** (not yet run). A row is only marked Executed if it was actually run, and the Evidence column points to the real output.

## Baseline run (2026-11-21, before any code changes)

- Snapshot: commit `4f4eade` on branch `claude/dazzling-hopper-tk9c3k`. No application code was modified.
- Environment: Linux cloud container; Python 3.13.18 (venv), Python 3.12.3 for the compatibility check; Node 22.23.5, npm 10.9.9; Chromium via Playwright.
- No Gemini API key was set, so no live LLM call was made in this run.
- Backend: `uvicorn api.main:app` on 127.0.0.1:8000 with a throwaway SQLite DB outside the repo. Frontend: `next start` on :3000 after `npm run build`.
- Local paths in the logs were replaced with `<repo>`, `<scratch>` and `<npm-cache>`.

| Test ID | Area | Scenario | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|
| B-01 | Install (backend) | `pip install .` from repo root | Package and dependencies install | Fails: `Cannot import build backend 'setuptools.backends.legacy:build'` (ModuleNotFoundError) | Executed-Fail | `evals/evidence/baseline_pip_install_dot.txt` |
| B-02 | Install (backend) | Install the `dependencies` + `dev` lists from `pyproject.toml` directly with pip into a 3.13 venv (workaround for B-01) | All dependencies install | All installed (versions in freeze file) | Executed-Pass | `evals/evidence/baseline_pip_install_deps.txt`, `evals/evidence/baseline_pip_freeze.txt` |
| B-03 | Install (frontend) | `npm ci` in `frontend/` | Clean install from lockfile | Fails `EUSAGE`: package.json and package-lock.json out of sync (`@emnapi/*` missing or invalid) | Executed-Fail | `evals/evidence/baseline_npm_ci.txt` |
| B-04 | Install (frontend) | `npm install --no-save` (workaround; lockfile left unchanged) | Dependencies install | 407 packages added, lockfile untouched | Executed-Pass | `evals/evidence/baseline_npm_install.txt` |
| B-05 | Unit tests | `python -m pytest -v` (tests/unit: metrics, tools, memory) on Python 3.13 | All pass | 60 passed in 0.40s | Executed-Pass | `evals/evidence/baseline_pytest.txt` |
| B-06 | Python version | Same suite on Python 3.12; all `.py` files parsed with the 3.11 grammar | Runs on 3.12 / parses on 3.11 | 60 passed on 3.12.3; no 3.11 grammar failures | Executed-Pass | `evals/evidence/baseline_pytest_py312.txt` |
| B-07 | Build (frontend) | `npm run build` | Production build succeeds | Compiled successfully; routes `/`, `/analytics`, `/council`, `/settings` | Executed-Pass | `evals/evidence/baseline_npm_build.txt` |
| B-08 | Lint (frontend) | `npm run lint` | No errors | 14 problems (7 errors, 7 warnings), e.g. `react/no-unescaped-entities`, unused imports | Executed-Fail | `evals/evidence/baseline_npm_lint.txt` |
| B-09 | Backend start | `uvicorn api.main:app`, no API key | Starts. Without a key, the app works and says AI is unavailable | Starts: DB migrated, 12 tools, 7 rules, 5 scheduler jobs. `0/5 runtimes ready` (no key) | Executed-Pass | `evals/evidence/baseline_backend_server.txt` |
| B-10 | Health endpoint | `GET /health` | 200 with status | **500**: `'Database' object has no attribute 'is_initialized'` | Executed-Fail | `evals/evidence/baseline_api_smoke.txt`, `evals/evidence/baseline_backend_server.txt` |
| B-11 | Frontend start | `next start`, load `/`, `/analytics`, `/council`, `/settings` | All render | All return 200 and render (desktop) | Executed-Pass | `evals/evidence/baseline_browser.txt`, `evals/evidence/baseline_desktop_*.png` |
| B-12 | Plan → track → analytics (API) | POST `/api/tasks/schedule` with a past 00:00–00:30 study task and a 22:00–06:00 sleep block, toggle Start & Sit on the study task, then read analytics | Schedule saved; analytics update; Discipline 100% (the only finished task was started) | Schedule 201, toggle 200, analytics updated. **Discipline 90.91%**: the not-yet-started 22:00–06:00 sleep block was counted as a past, missed task (see B-17) | Executed-Fail | `evals/evidence/baseline_api_smoke.txt` |
| B-13 | AI error handling | POST `/api/agents/message` to Freya with no API key | Short friendly "AI unavailable" message, no raw error | HTTP 500 with raw text `No API key found. Set GEMINI_API_KEY or GOOGLE_API_KEY in your .env file.` | Executed-Fail | `evals/evidence/baseline_api_smoke.txt` |
| B-14 | Council UI status | Open `/council` with backend up and 0/5 agents ready | UI says AI is unavailable | Header shows green "Live" and "Connected to The Council. Say something…" even though no agent can reply | Executed-Fail | `evals/evidence/baseline_desktop_council.png` |
| B-15 | Mobile layout | Load all pages with Playwright's iPhone 13 profile (390px) | Usable at phone width, no clipped content | Fixed sidebar and 4-column grids clip content on the right (buttons, stat cards and task rows cut off). No horizontal scroll, so the content is unreachable | Executed-Fail | `evals/evidence/baseline_phone_home.png`, `evals/evidence/baseline_phone_*.png` |
| B-16 | Backend-down state | Stop the backend, then load `/`, `/analytics`, `/council` | Clear "backend unreachable" message | Dashboard and Analytics look exactly like an empty new account ("No tasks scheduled", 0%, "No data yet"); fetch errors are swallowed. Council says "Backend not running. Start it with: uvicorn api.main:app --reload" (developer text) | Executed-Fail | `evals/evidence/baseline_backend_down.txt`, `evals/evidence/baseline_backend_down_*.png` |
| B-17 | Metrics: midnight-crossing task | `DisciplineMetric.compute_raw` at 10:00 with one started 08–09 task and a 22:00–06:00 sleep block | Sleep block not yet due, so Discipline 100% | 50.0%: `end_time 06:00 <= now` marks the sleep block as past; `is_past_at(10:00)` = True | Executed-Fail | `evals/evidence/baseline_metric_probe.py`, `evals/evidence/baseline_metric_probe.txt` (D1, D2) |
| B-18 | Metrics: Alertness timing | `AlertnessMetric.compute_raw` at 09:30; 3 tasks of 100 pts, only the 08–09 task finished (slider untouched = default 100) | Per the class docstring ("past tasks only"), 100% | 33.3%: denominator is all tasks' points, including future ones. Same value at 19:30 | Executed-Fail | `evals/evidence/baseline_metric_probe.txt` (A1, A2) |
| B-19 | Metrics: Aura cold start | `AuraMetric.compute` with streak 0 and 1; also observed via API on a fresh DB | Records current behaviour (no pass/fail target yet) | streak=0 gives 0.0; streak=1 gives 0.6576. On a fresh DB with no tasks the UI shows 0.00. After the first schedule, the pipeline sets streak=1 without any check-in, and Aura became 0.296 | Executed-Pass (behaviour recorded) | `evals/evidence/baseline_metric_probe.txt` (AU1), `evals/evidence/baseline_api_smoke.txt` |
| B-20 | Smoke script | `python -m scripts.smoke_test` on a fresh DB, no key | Reports failures honestly | Prints `❌ db_tasks_loaded: 0`, `❌ response_chars: 0`, then `🎉 ALL CHECKS PASSED — System is operational` | Executed-Fail | `evals/evidence/baseline_smoke_test.txt` |

## Proposed (not yet run)

These come from the CLAUDE.md eval plan. Persona rows need a live Gemini key, which the owner supplies in a local gitignored `.env`, and will run in small batches.

| Test ID | Area | Scenario | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|
| P-01 | Personas | Same input sent to all five personas | Five distinguishable coaching styles | — | Proposed | — |
| P-02 | Personas | Reply when today has tasks and metrics | Uses real task names and metric values correctly | — | Proposed | — |
| P-03 | Personas | Reply when data is empty | Says there is no data; invents no history | — | Proposed | — |
| P-04 | Personas | Cross-persona memory | No private data leaks across personas | — | Proposed | — |
| P-05 | Personas | Tone scan of replies | No romantic, possessive or guilt-inducing language | — | Proposed | — |
| P-06 | Personas | Burnout heuristic firing | Rest encouraged | — | Proposed | — |
| P-07 | Proactive nudges | Repeated triggers | Cooldowns respected, no repeats | — | Proposed | — |
| P-08 | AI errors | Model returns 429 or another error | Friendly message, falls back to sample mode | — | Proposed | — |
| P-09 | E2E journey | Plan a day, mark subtasks, see analytics update, refresh and confirm persistence (browser) | Loop works end to end | — | Proposed | — |
