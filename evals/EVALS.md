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

## After fixes (re-run 2026-11-21, after commits up to `2e894e9`)

Same environment as the baseline (Linux container, Python 3.13.18 venv plus 3.12.3 and 3.11.18 venvs, Node 22.23.5, Chromium via Playwright). There was still no Gemini API key, so no live LLM call was made. The backend ran on a fresh scratch database.

| Test ID | Area | Scenario | Expected | Actual (after fixes) | Status | Evidence |
|---|---|---|---|---|---|---|
| B-01 | Install (backend) | `pip install .` in a fresh Python 3.13 venv (also run on 3.12) | Installs | `Successfully built feynlist` / installed on 3.13 and 3.12 | Executed-Pass | `evals/evidence/after_B01_pip_install_dot.txt`, `evals/evidence/after_pip_install_dot_py312.txt` |
| B-02 | Install (backend) | Dependency install | Installs | Covered by B-01 (`pip install .` now installs all dependencies) | Executed-Pass | `evals/evidence/after_B01_pip_install_dot.txt` |
| B-03 | Install (frontend) | `npm ci` from a deleted `node_modules` | Clean install from lockfile | 403 packages added; lockfile regenerated and in sync | Executed-Pass | `evals/evidence/after_npm_ci.txt` |
| B-04 | Install (frontend) | `npm install --no-save` workaround | Not needed any more | Superseded by B-03 | Executed-Pass | `evals/evidence/after_npm_ci.txt` |
| B-05 | Tests | Full pytest suite on Python 3.13 | All pass | 125 passed (60 original unit tests, some rewritten for the new metric definitions, plus 65 new) | Executed-Pass | `evals/evidence/after_pytest_py313.txt` |
| B-06 | Python version | Full suite on 3.12 and 3.11; `requires-python` lowered to >=3.11 | Pass | 125 passed on 3.12.3; 125 passed on 3.11.18 | Executed-Pass | `evals/evidence/after_pytest_py312.txt`, `evals/evidence/after_pytest_py311.txt` |
| B-07 | Build (frontend) | `npm run build` | Succeeds | Compiled; routes `/`, `/about`, `/analytics`, `/council` (Settings removed) | Executed-Pass | `evals/evidence/after_npm_build.txt` |
| B-08 | Lint (frontend) | `npm run lint` | No errors | 0 errors, 0 warnings, exit 0 | Executed-Pass | `evals/evidence/after_npm_lint.txt` |
| B-09 | Backend start | `uvicorn api.main:app`, no key | Starts, says AI is unavailable | Starts; log says agents failed to init with reason `no_api_key`; no tracebacks | Executed-Pass | `evals/evidence/after_backend_server.txt` |
| B-10 | Health endpoint | `GET /health` | 200 | 200 `{"status":"healthy","db_ok":true,...}` | Executed-Pass | `evals/evidence/after_api_smoke.txt` |
| B-11 | Frontend start | Load all routes | Render | `/`, `/analytics`, `/council` return 200. `/settings` now returns 404 (intentionally removed; replaced by `/about`) | Executed-Pass | `evals/evidence/after_browser_pages.txt` |
| B-12 | Plan → track → analytics (API) | Same calls as baseline: past 00:00–00:30 study task plus a 22:00–06:00 sleep block, Start & Sit on the study task | Discipline 100%, sleep block not missed | Schedule 201, toggle 200, **Discipline 100.0** | Executed-Pass | `evals/evidence/after_api_smoke.txt` |
| B-13 | AI error handling | POST `/api/agents/message` to Freya, no key | Friendly message, no raw error | HTTP 503 `Live AI replies aren't set up on this server...`; no env var or `.env` text | Executed-Pass | `evals/evidence/after_api_smoke.txt` |
| B-14 | Council UI status | Open `/council` with 0 agents ready | Says AI is unavailable | Header: `Connected · AI replies unavailable` | Executed-Pass | `evals/evidence/after_council_status.txt`, `evals/evidence/after_desktop_council.png` |
| B-15 | Mobile layout | 8 views at 390px (iPhone 13 profile) and 1366px: home, task expanded, planner, check-in, Aura info, analytics, council, about | Nothing clipped | 0 elements past the viewport and 0 page errors on all 16 views. The same script on baseline code found 73 (home), 64 (planner), 177 (Aura info), 4 (analytics), 1 (council) | Executed-Pass | `evals/evidence/after_responsive_check.txt`, `evals/evidence/before_responsive_check.txt`, `evals/evidence/after_phone_*.png`, `evals/evidence/before_phone_*.png` |
| B-16 | Backend-down state | Backend stopped; load `/`, `/analytics`, `/council`; then start the backend | Clear unreachable message; recovers | Banner on all three pages, no empty-account text, no `uvicorn` instructions. Banner gone ~5s after the backend started, without a manual reload | Executed-Pass | `evals/evidence/after_backend_down.txt`, `evals/evidence/after_backend_down_*.png`, `evals/evidence/e2e_backend_down_recovery.txt` |
| B-17 | Metrics: midnight-crossing task | Discipline at 10:00 with a started 08–09 task and a 22:00–06:00 sleep block | 100% | 100.0; `is_past_at(10:00)` = False; active at 23:00 | Executed-Pass | `evals/evidence/after_metric_probe.txt` (D1, D2) |
| B-18 | Metrics: Alertness timing | 09:30; 08–09 task finished with focus 100; two future tasks | 100% | 100.0 at 09:30 and at 19:30. Note: re-running the *baseline* probe unchanged gives 0.0, because it builds a task marked completed but not attentive, which the app never saves; under the new definition that counts as "nothing rated" | Executed-Pass | `evals/evidence/after_metric_probe.txt` (A1–A3), `evals/evidence/after_baseline_probe_rerun.txt` |
| B-19 | Metrics: Aura cold start | Aura on day 1 / streak 0 | Records behaviour | Formula unchanged (streak 0 gives 0.0). The streak no longer auto-starts at 1 just because tasks exist (API showed streak 0, Aura 0.0, check-in `null`), and the UI shows "—" with "Starts after your first counted day". Without Study blocks, a perfect 3-day streak gives 1.39 instead of being capped at ×0.45 | Executed-Pass (behaviour recorded) | `evals/evidence/after_metric_probe.txt` (AU1), `evals/evidence/after_api_smoke.txt`, `evals/evidence/after_phone_home.png` |
| B-20 | Smoke script | `python -m scripts.smoke_test`, no key; then with `--require-llm` | Honest report | `4 passed, 0 failed, 1 skipped` / `RESULT: PASSED WITH SKIPS: live_llm not tested`, exit 0; with `--require-llm` exit 2. Failure path (exit 1) covered by a unit test | Executed-Pass | `evals/evidence/after_smoke_test.txt`, `tests/unit/test_smoke_script.py` |

### New automated tests (all executed in B-05; 125 passed)

| Test ID | Area | Scenario | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|
| T-01 | Check-in & streak (API, temp DB) | "Yes" starts the streak; "Not today" resets it; scheduling alone doesn't grow it; it carries over from a counted yesterday; the old payload is rejected | As described | 5/5 passed | Executed-Pass | `tests/integration/test_checkin_api.py`, `evals/evidence/after_pytest_py313.txt` |
| T-02 | Streak rules (unit) | Threshold, in-progress day, no-task check-in, new user | As described | 8/8 passed | Executed-Pass | `tests/unit/test_metrics.py::TestConsistencyStreakMetric` |
| T-03 | Personas (static) | Required fields, banned-term scan (the old personas fail it), shared rules present, five distinct roles, `model_tier` only | As described | 16/16 passed | Executed-Pass | `tests/unit/test_personas.py` |
| T-04 | AI errors (API + websocket, stubbed provider) | No key, and a stubbed 429 with provider text, over REST and websocket; error classification; status flag; personas resolve to Flash models | Friendly text only, no raw provider text | 11/11 passed | Executed-Pass | `tests/integration/test_agent_errors_api.py` |
| T-05 | Metrics (unit) | Alertness new definition, midnight-crossing tasks, Study factor, burnout skips unrated days | As described | All passed (41 tests in file) | Executed-Pass | `tests/unit/test_metrics.py` |
| T-06 | Truncation (unit, stubbed client) | Thinking budget 0 sent; MAX_TOKENS detected; reply trimmed to the last full sentence | As described | 7/7 passed | Executed-Pass | `tests/unit/test_response_parser.py` |
| T-07 | Template | Only picker classes; one midnight-crossing Sleep block that isn't counted missed; saves through the API | As described | 4/4 passed | Executed-Pass | `tests/integration/test_day_template.py` |
| T-08 | Health | `/health` 200 with `db_ok` | As described | 1/1 passed | Executed-Pass | `tests/integration/test_health_api.py` |
| T-09 | Smoke script | Skip reported honestly; `--require-llm` gives exit 2; failure/crash gives exit 1 | As described | 3/3 passed | Executed-Pass | `tests/unit/test_smoke_script.py` |

### Cut list, demo mode and free-tier budget (executed 2026-11-21, commits up to `575f49f`)

Full suite after these changes: **168 passed** on Python 3.13 (`evals/evidence/after_pytest_py313_step8.txt`). The model is stubbed or absent in every test below; **no live Gemini call was made**.

| Test ID | Area | Scenario | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|
| T-10 | Triggers | Every routed event has an emitter in the code and a dispatching rule; persona YAML lists exactly its routed events; the 5 unemitted triggers aren't claimed; wiring twice doesn't double-dispatch | As described | 12/12 passed | Executed-Pass | `tests/unit/test_triggers.py` |
| T-11 | Task-completed event | Completing a task (shortcut or last subtask) emits TASK_COMPLETED once; re-completing or un-completing doesn't | As described | 2/2 passed | Executed-Pass | `tests/integration/test_task_completed_event.py` |
| T-12 | Percentile | Fewer than 14 days of history: tool and endpoint say "not enough history"; after 14 days: a percentile | As described | 2/2 passed | Executed-Pass | `tests/integration/test_percentile_history.py` |
| T-13 | Demo sessions (API) | No/invalid session id → 400; new session seeded with 14+ days and a 12-block plan; two sessions isolated; reset restores sample; browser zone decides "today" (UTC+14 vs UTC−11); concurrent first requests seed once; LRU eviction deletes files; demo endpoints off without demo mode | As described | 8/8 passed | Executed-Pass | `tests/integration/test_demo_sessions.py` |
| T-14 | Demo controls (API, stubbed model) | missed-task → Freya, complete-task → Albedo, end-of-day → Anya, check-in → ZeroTwo; repeated controls bypass cooldowns; complete-task completes one block; nudges are per session; websocket push reaches only that session's socket; chat not blocked by the global cooldown | As described | 9/9 passed | Executed-Pass | `tests/integration/test_demo_triggers.py` |
| T-15 | Free-tier budget (API, stubbed model) | 2 live replies then samples; chat + demo controls share the budget; reset doesn't refill; per-session budgets; global daily cap; per-minute guard; a failed call refunds the session; Council (all five) and automatic nudges are free samples; no scheduled LLM jobs by default | As described | 10/10 passed | Executed-Pass | `tests/integration/test_ai_budget.py` |
| T-16 | Sample mode, no key (API + websocket) | No key → labelled sample (not 503); stubbed 429 → labelled sample, no provider text over REST or websocket | As described | Passed (part of T-04 file, 13 tests) | Executed-Pass | `tests/integration/test_agent_errors_api.py` |
| E-01 | E2E demo mode (browser) | Two browsers (desktop + phone) on a DEMO_MODE backend: each sees its own seeded data; "Complete a task" control moves 7/12 → 8/12 in one session only; reset restores 7/12; analytics shows charts | As described | As expected, no page errors | Executed-Pass | `evals/evidence/e2e_demo_mode.txt`, `evals/evidence/demo_*.png` |
| E-02 | E2E sample mode (browser, no key) | Council shows "Showing sample replies (no live AI on this server)." and the free-API notice; Freya's chat reply and a missed-task nudge both carry "Sample reply (pre-written, not live)" plus the reason; samples use only real numbers ("7 of 12 blocks", the real task name) | As described | As expected, no page errors | Executed-Pass | `evals/evidence/e2e_sample_mode.txt`, `evals/evidence/sample_mode_*.png` |
| E-03 | E2E cold start (browser) | Backend down: "Waking the server, this can take up to a minute…" (no empty-account text); backend started: page loads by itself ~5 s later | As described | As expected | Executed-Pass | `evals/evidence/e2e_backend_down_recovery.txt` |
| E-04 | Phone layout, demo mode | Same 16-view overflow check with the new demo and nudge panels | 0 overflow, 0 page errors | 0 / 0 on all 16 views | Executed-Pass | `evals/evidence/after_responsive_check.txt` |

### Deployment (executed 2026-11-22 against the live URLs)

Backend `https://feynlist-api.onrender.com` (Render, free plan), frontend `https://feynlist.vercel.app` (Vercel). Run with `python -m scripts.check_deploy --api ... --web ...`.

| Test ID | Area | Scenario | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|
| D-01 | Deployed evaluator journey | health; demo mode; sample plan + 14-day history; task toggle updates analytics; one coach reply; budget; session required; CORS; frontend 200; websocket over wss | All pass, coach reply live | Health 200 (5 agents ready, so the key is loaded); sample data seeded; toggle 0 → 30 points; session-less request 400; frontend 200; **wss connects**. **Live reply failed with a non-quota provider error and fell back to a labelled sample.** Likely cause: the configured `gemini-2.5-flash` models were reportedly shut down on 2026-10-16 (not confirmed from Render logs). **CORS returned `*`** (`ALLOWED_ORIGINS` not yet set to the Vercel URL). The script originally accepted `*`; fixed so it now fails. | Executed-Fail (live AI, CORS) | `evals/evidence/check_deploy_live.txt` |

### Still open / not verified

- **No live model call has been made in any eval.** The live path of the budget (2 live replies, then samples), the truncation fix (issue 4) and all persona behaviour are verified only with a stubbed model. They need a small live batch with the owner's key (P-01 to P-09).
- **Sample replies were written in this session (Claude Code), in each coach's style.** They are checked to use only real session facts, but nobody else has reviewed them.
- **Budget counters live in a file on the server.** On a free host with an ephemeral disk, a restart resets them; Google's own quota (429 → labelled sample) is then the backstop. Clearing browser storage creates a new session with 2 new live replies; the global daily cap bounds the total.
- **Not built:** the optional "use your own Gemini key" field.
- **Not deployed yet.** No checks have been run against live URLs (Vercel/Render), and there is no deploy kit (`render.yaml`, `DEPLOY.md`) yet.
- **Screenshots** capture the visible screen only, because pages scroll inside the main area.

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
| P-08 | AI errors | A *live* model returns 429 or another error | Friendly message, falls back to sample mode | Friendly message verified with a stubbed provider only (T-04); sample-mode fallback not built yet | Proposed | — |
| P-09 | Truncation (live) | Several live persona replies at max_output_tokens=300 with thinking off | No reply ends mid-sentence | — | Proposed | — |
| P-10 | E2E journey | Plan a day, mark subtasks, see analytics update, refresh and confirm persistence (browser) | Loop works end to end | — | Proposed | — |
