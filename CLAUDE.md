# Feynlist — Groww Case Study Handoff (for Claude Code)

You are improving an existing project so it can be submitted as a Groww product case study ("Pick a real problem you've seen up close and design a digital app to solve it"). The owner built Feynlist for their own use; two friends later used it during exam prep and gave the owner direct feedback. This is a product-thinking assignment judged on honest problem framing, sensible scope, working execution and truthful validation, not on engineering flash.

## Hard rules

1. **Do not write the one-page write-up (Deliverable 1).** Groww requires it to be the owner's own words. You may review a draft the owner writes, point out gaps, and check claims against the evidence register below. Never produce a final page for them.
2. **Never fabricate history or results.** Do not invent development prompts, user counts, test results, screenshots or metrics. Every test in the eval file is marked `Executed` (with real output) or `Proposed` (not yet run). Never mark a test Passed without running it.
3. **Keep prompts honest.** Record any prompt the owner pastes as `Historical (provided by owner)`. Record prompts used in this session as `New improvement prompt`. Persona prompts that already exist in the repo are `Present in repo (origin date unknown)`. Do not reconstruct a past development history.
4. **No secrets or personal data in the repo.** No API keys, `.env`, local paths (e.g. `d:\feynlistV1`), or private biographical details. Ask before any git push or deploy.
5. **Prefer targeted edits over rewrites.** Keep the architecture. Make changes small and reviewable, one commit per logical change.

## Product in one line

An accountability-first productivity app: plan the day, track whether you showed up, finished and stayed attentive, see your progress, and get context-aware coaching from five AI personas ("The Council"). Loop: Plan → Work → Track → Reflect → Receive relevant accountability → Improve the next plan.

## Stack (verified from the repo)

- Backend: Python 3.13, FastAPI, aiosqlite (SQLite), APScheduler, Gemini via `google-genai`. Entry: `api.main:app`. Tests: `tests/unit/` (metrics, tools, memory); no integration tests.
- Frontend: `frontend/` Next.js 16, React 19, Tailwind 4, Recharts. API base from `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`), websocket at `/api/agents/ws`.
- Scoring: task points split 50% Start & Sit / 30% Complete / 20% Be Attentive (slider). Discipline, Alertness, PS Hours, Aura, streak are in `analytics/metrics.py`. Burnout is a rule-based heuristic in `analytics/trends.py`, not a validated measure; never present it as clinical.

## Evidence register (what the owner can truthfully claim)

Claimable: the owner personally struggled with accountability while working alone; informal conversations with college-student friends and remote-working friends described similar problems (number of people and method not recorded); the owner built the app for themselves; progress graphs and streaks motivated them (self-reported); the Council made solo work more engaging for them (self-reported); two friends used it during exam prep and told the owner directly that it helped (the owner recalls the feedback as positive; the specific points reported by at least one friend were: returned to their desk more often, improved their schedule, could see where their time went and how much work they finished). Wording in any artifact must say "two friends" and attribute each specific point only to those who actually said it; ask the owner if unsure. All self-reported, no measurements.

Not established, never claim: any productivity percentage, clinical burnout prevention, reduced loneliness, five personas beating one, retention, equal effectiveness for remote workers, market size, competitor claims.

## Known issues to fix (found in review)

1. **Check-in modal** in `frontend/src/app/DashboardClient.tsx` asks an explicit sexual question and labels a button "Yes (Relapsed)"; the answer drives the streak and Aura. Replace with a neutral, generic consistency check-in (e.g. streak continues if the user completed at least a user-chosen share of their plan, or taps "I kept my commitment today"). Rename "Retention Streak"/`relapsed` in UI copy; keep DB column compatibility or add a migration. Remove `STREAK_BREAK_SUBCLASS=Semen_wasted` from `.env.example`.
2. **Personas** (`agents/personas/*.yaml`): currently romantic/possessive ("the user's wife", etc.) and contain private biographical details and an "addiction fight" reference. Rewrite as five distinct coaching styles. Keep the names (Freya, Anya, ZeroTwo, Albedo, Mohini), roles, triggers, cooldowns and tool lists. Suggested styles: Freya direct/honest, Anya warm/rest-aware, ZeroTwo analytical, Albedo playful celebrator, Mohini calm/energy-focused. Rules for all: no romantic or possessive framing, no body or addiction commentary, never invent history (say when there is no data), never guilt the user into overworking, encourage rest when the burnout heuristic fires, short casual replies.
3. **Quota failures:** Anya uses `gemini-2.5-pro`, which has zero free-tier quota, so every Anya reply fails and the raw 429 error text is shown in chat. Route all personas to Flash/Flash-Lite via settings. Catch model errors in `agents/runtime.py` and the websocket and show a short friendly message; never expose raw provider errors.
4. **Truncated replies:** one recorded Freya reply cut off mid-sentence. Check `max_output_tokens` and response parsing in `agents/response_parser.py`.
5. **Alertness formula:** the docstring says past tasks only, but the code sums all tasks' points in the denominator, deflating early-day Alertness and possibly triggering a false "mild burnout" when the slider is unused. Decide the intended behavior, fix, and add tests.
6. **Aura is 0.00 for any new user** (`log(1+0)=0`). Fix the cold-start experience without changing the intent, and document the formula in the UI info banner.
7. **Settings page is dead:** it writes `api_url` to localStorage but `frontend/src/lib/api.ts` never reads it, and it shows a local path. Either wire it up or remove it.
8. **Silent failures:** `app/page.tsx` and `analytics/page.tsx` swallow fetch errors. Show a clear "backend unreachable" state.
9. **Developer debug panel and token stats** are shown to everyone. Hide behind a toggle (default off) but keep the token usage view, since AI usage visibility is a feature.
10. **Author-specific defaults:** task classes and the template are tuned to one person's routine. Make the template generic and student-friendly; keep `Academics_Selfstudy` but do not make Aura depend on it for non-students (document the choice). Test the template's midnight-crossing sleep block (22:00–06:00).
11. `pyproject.toml` build backend `setuptools.backends.legacy:build` looks invalid; verify with `pip install .` and fix to `setuptools.build_meta`.
12. Persona config path default in `config/settings.py` (`config/persona_configs`) does not exist; personas load from `agents/personas`. Remove the dead setting or point it correctly.

## Cut list: remove or hide anything that doesn't serve the loop

A reviewer should see a small, focused prototype. Remove (or hide) the following, verifying with `grep` before deleting anything:

- **Settings page** and its sidebar entry. Replace with a small "About this demo" panel (sample-data notice, how the Council uses your data, reset button). The backend URL field is dead code.
- **Legacy and author-only scripts**: `scripts/migrate_csv_to_sqlite.py`, `scripts/fix_existing_ps_hours.py`, `scripts/verify_db.py`, CSV references in the README, and the unused `gui` extras (tkinter, matplotlib, plyer) in `pyproject.toml`. Drop `pandas` and `asyncio-throttle` if nothing else imports them. Keep `scripts/smoke_test.py` if it works.
- **Subscription tiers** (free/pro/ultra) and the placeholder `users` table: replace with one simple per-session and global daily interaction limit.
- **Unused task classes** (`Side_Business`, `ExtraActi`, `Social`, `Self_Growth`, `Deviated`, `revived` in the picker). Offer a short student-friendly list: Study, Class, Project/Work, Reading, Wellness, Break, Sleep. Keep Deviated/revived only if the scoring code needs them internally.
- **"Percentile" quick action and any UI that only makes sense with months of history.** New and demo users should never see empty or meaningless widgets.
- **Developer debug panel**: hidden by default behind a toggle. Keep the token usage view (AI usage visibility).
- **Persona triggers that nothing emits.** `INACTIVITY_DETECTED`, `LOW_ENERGY_DETECTED`, `HIGH_SCORE`, `PERFORMANCE_DROP`, `WEEK_REVIEW` appear in persona configs and the orchestrator map but I did not find emitters for them. Verify with `grep`; either implement a simple emitter (e.g. no task started for 90 minutes; discipline drops 20 points vs 7-day average) or delete the claim from persona configs and docs. Do not document behavior that doesn't exist.
- **README claims** like "professional-grade" and "proprietary scoring". Rewrite it honestly and short: what it is, how to run it, how to evaluate it, known limits.
- **Everything with the author's local paths, timezone and routine baked in** (Asia/Kolkata hardcoded in the scheduler and users table, default 06:00 to 22:00 template). Use the browser timezone for display and a session timezone setting.

Keep (these are the product): the task planner and 3-part scoring, Discipline and Focus (Alertness) scores, Aura as a simple momentum score with an explanation, streak, 14-day charts, burnout heuristic labeled as a workload signal, the Council chat (individual and all-five), proactive nudges, memory, and the token usage view.

## Demo controls (so evaluators can see proactive behavior without waiting)

The scheduler fires at fixed clock times and every 20 minutes to 2 hours, which an evaluator will never wait for. Add a visible "Demo controls" menu with: Load sample two-week history, Mark a task as missed (triggers Freya), Complete a task (triggers Albedo), Simulate end of day (Anya/Mohini review and streak check), Trigger a check-in (ZeroTwo), and Reset demo. These call the same event paths as the real scheduler, so evaluators see the real behavior. Respect global cooldowns, but let demo controls bypass them with a clear "demo mode" label.

## Free-tier AI budget (the owner will NOT enable billing)

The prototype must run entirely on a free-tier Gemini key. Free-tier limits apply per Google Cloud project (not per key), requests per day reset at midnight Pacific time, and the current numbers are visible only in the owner's AI Studio rate-limit page; do not hardcode assumed limits. Free-tier content may also be used by Google to improve its products.

Rules:
1. **2 live AI replies per evaluator session.** One persona reply = 1 live reply. Count chat messages and demo-control nudges together. Store the counter server-side keyed to the session, not in the browser.
2. **Global daily cap** for all live calls, configured by an env var (`LIVE_AI_DAILY_CAP`) that the owner sets below their AI Studio daily request limit, with headroom for the owner's own evals. Also respect per-minute limits with a small queue or a friendly "try again in a moment". When the cap is reached, everyone falls back to sample mode.
3. **Council (all five) is not live in the public demo**: it would spend five requests at once. Show it in sample mode.
4. **Disable all scheduled LLM calls in the public demo.** The scheduler's 20-minute and 2-hour jobs would burn the daily quota with nobody present. Scheduled jobs may still compute analytics (no LLM). Keep the full scheduler for local/real use behind a `ENABLE_PROACTIVE_LLM=true` flag.
5. **Sample mode (the fallback).** After a session's 2 live replies, or when the cap, quota or model fails, show pre-written example replies for each persona and each trigger (missed task, task completed, end-of-day, check-in, rest nudge), generated from the real persona style and the sample data. Every sample reply must carry a visible label: "Sample reply (pre-written, not live)". Never present a sample as a live reply. Sample replies must not claim data the user doesn't have.
6. **Models:** use Flash-Lite or Flash only; pick whichever has the higher free daily allowance in the owner's AI Studio; make the model names env vars. Keep `max_output_tokens` low (about 200 to 300) and context small to save tokens.
7. **UI:** show "Live replies left: N of 2" and, when exhausted, "Showing sample replies." Show a short notice: "Live replies use a free Google API; don't enter personal information. This demo uses sample data."
8. **Errors:** never show raw provider errors. Map 429 and other failures to sample mode with a friendly line.
9. **Optional stretch (only if everything else is done):** a "use your own Gemini key" field for evaluators who want unlimited live chat. Keep the key in memory for that session only, never log or store it, and send it server-side over https only.
10. **Honesty in docs:** the README and the in-app "About" must say that the Council is designed to run live with all five personas and proactive nudges, that the public demo limits live replies to 2 per session to stay on a free key, and that the remaining behavior is shown as labeled samples. Do not claim persona behavior was tested unless an `Executed` eval proves it.

Evals under free-tier limits: run persona evals in small batches (a handful of calls at a time, spread across days if needed), log the exact model and date, and mark anything not run as `Proposed`.

## Evaluator access (Deliverable 4)

Evaluators must be able to use the app with no setup and no personal history.

- Add a clearly labeled **Demo mode**: seeded sample tasks and about two weeks of sample metrics, labeled "Sample data" in the UI. No real user data in the demo.
- **Isolate each evaluator session** (separate SQLite file or user row keyed by a session id cookie) so people don't see or overwrite each other. Add a reset-demo button.
- **Protect the Gemini key:** server-side only, and follow the "Free-tier AI budget" section below. If the model is unavailable, the app must still work and say so.
- **Hosting model (owner has only hosted frontends before; assume zero backend experience).** Frontend on Vercel (Root Directory `frontend`, env `NEXT_PUBLIC_API_URL` set to the backend URL before the build). Backend as a single Python web service on a free host that deploys from GitHub (Render is the default suggestion; verify the host's current free plan, and offer Railway, Fly or a Docker-based host as alternatives). Needs: websocket support, wss over https, CORS limited to the frontend origin (`ALLOWED_ORIGINS` env var).
- **No persistent disk required.** The public demo uses seeded sample data and per-session databases, so SQLite may live in ephemeral storage (e.g. `/tmp`) and may reset on restart. State this in the About panel. Do not design anything that needs paid storage.
- **Python version:** many hosts don't offer 3.13. Check whether the code uses any 3.13-only feature; if not, lower `requires-python` to 3.11 or 3.12 and pin the host's Python version via env var or config file.
- **Cold starts:** free backends usually sleep when idle. Add a friendly loading state on the frontend ("Waking the server, this can take up to a minute") with retry on `/health`, and a `/health` endpoint cheap enough to ping. Tell the owner to open the app once shortly before submitting.
- **Deliver a deploy kit:** a config file for the backend host (e.g. `render.yaml`), a `vercel` setup note, a `.env.example` listing every variable with a plain description, and `DEPLOY.md` with click-by-click steps for someone who has only deployed frontends, including exactly what to type into each dashboard field and where each secret goes.
- **Secrets:** the Gemini key is typed by the owner into the backend host's dashboard only. Never ask the owner to paste keys into chat, never commit them, never write them into files that aren't gitignored. Claude Code does not need the production key to deploy; it needs a key only in a local, gitignored `.env` if the owner chooses to run live persona evals.
- **Verification after deploy:** run a scripted check against the live URLs (health, schedule creation, task toggle, analytics, one sample-mode reply, one live reply if quota allows, websocket connect over wss, a browser pass in a private window and at phone width). Fix failures and redeploy until the evaluator journey passes, and record results in `EVALS.md`.
- Provide a short "How to evaluate in 3 minutes" panel on the first screen.
- Tell the owner which accounts, env vars and logins are needed. Do not deploy without their go-ahead.

## Evals (Deliverable 3)

Create `evals/EVALS.md` with this table, one row per test:

`Test ID | Area | Scenario | Expected | Actual | Status (Executed-Pass / Executed-Fail / Proposed) | Evidence (command output, log path or screenshot path)`

Run what you can for real: pytest for metrics, tools, memory; new unit tests for point splits, streak resets and date boundaries, empty and partial datasets, midnight-crossing tasks; API tests with a temp database; Playwright or browser runs for the end-to-end journey (plan a day, mark Start & Sit, Complete and Be Attentive, see analytics update, refresh and confirm persistence, empty new-user state, backend-down state, mobile layout). Save screenshots to `evals/evidence/`.

LLM/persona evals (run against the live key only if the owner supplies one; otherwise mark Proposed): five personas are distinguishable on the same input; replies use real metrics and task names correctly; no invented history when data is empty; no private data leaks across personas; no romantic, possessive or guilt-inducing language; rest encouraged on high workload; proactive messages respect cooldowns and don't repeat; model failure shows a friendly message. Record failures and fixes honestly, including any that remain open.

## Prompt record (Deliverable 2)

Maintain `prompts/PROMPTS.md` with three clearly separate sections: (A) Historical prompts provided by the owner (empty until they provide them), (B) Persona and system prompts present in the repo, labeled with their file paths and "origin date unknown", (C) New improvement prompts used in this session, in order, with what each changed. Never move anything between sections to make the history look better.

## Order of work

1. Run the existing tests; record results in EVALS.md.
2. Fix issues 1–3, 5–6 first (they block a credible demo), then 4, 7–12.
3. Add demo mode and session isolation; add the evaluator panel.
4. Write and run the evals; fix what fails; keep failures documented.
5. Prepare deploy config and instructions; stop and ask the owner before deploying.
6. Final check: fresh clone, install, run, evaluator journey works from the deployed URL; `git grep` for secrets, local paths and the removed terms.

## Definition of done

A stranger can open the link, try the demo in three minutes, and see the plan-track-reflect-coach loop working; no explicit or private content anywhere in UI, prompts, config or repo; EVALS.md shows real executed results with evidence and honest open issues; PROMPTS.md separates historical from new; the owner has everything they need to write Deliverable 1 themselves.
