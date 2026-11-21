# Feynlist

An accountability-first day planner. You plan your day in time blocks, mark each one as you go, see how you actually did, and get short coaching from five AI personas ("The Council").

**Loop:** plan → work → track → reflect → get relevant accountability → plan the next day better.

## What it does

- **Plan** the day as time blocks (Study, Class, Project / Work, Reading, Wellness, Break, Sleep). Blocks may cross midnight (e.g. Sleep 23:00–07:00).
- **Track** each block with three marks, which give its points:
  - Start & Sit: 50%
  - Complete: 30%
  - Be Attentive: 20%, scaled by your focus rating
- **See progress:**
  - **Discipline:** share of finished blocks you started.
  - **Alertness:** focus on the blocks you rated.
  - **Study hours.**
  - **Consistency streak:** days you checked in "Yes" or finished at least 50% of your plan.
  - **Aura:** a simple momentum score; the formula is shown in the app.
  - 14-day charts.
  - A **workload signal:** a rule-based heuristic, not a medical assessment.
- **Get coaching** from five personas with different styles:

| Coach | Style | Speaks on its own when |
| :--- | :--- | :--- |
| Freya | Direct and honest | A task is missed; the day starts |
| Anya | Warm, rest-aware | Workload signal is moderate/severe; streak breaks; end-of-day review |
| ZeroTwo | Analytical | Scheduled check-in |
| Albedo | Playful celebrator | A task is completed; streak milestone |
| Mohini | Calm, energy-focused | Only when you message her |

All five reply when you message them directly. "Hi council" asks all five at once.

### Live AI vs. sample replies (free-tier budget)

The Council is designed to run live: all five personas, plus proactive nudges. The public demo runs on a free Gemini key, so it limits live replies:

- **2 live replies per browser session.** Chat and demo controls count together.
- **A global daily cap** (`LIVE_AI_DAILY_CAP`) and a per-minute guard.
- **Always samples:** "Council" (all five at once) and automatic nudges.
- **No scheduled model calls.** They run only with `ENABLE_PROACTIVE_LLM=true`, for local use.

Everything else, and every case where the AI is unavailable (no key, quota, error), is shown as a **pre-written sample reply**. It is always labelled "Sample reply (pre-written, not live)" and uses only the session's real numbers.

### Demo mode (for evaluators)

With `DEMO_MODE=true`, each browser session gets its own temporary database:

- **Sample data:** about two weeks of made-up history, labelled in the UI.
- **Separate per evaluator:** nobody sees anyone else's session.
- **Browser timezone:** "today" and "missed" follow the evaluator's clock.
- **"How to evaluate in 3 minutes":** a panel on the first screen.
- **Demo controls:** fire the real proactive paths immediately, with cooldowns bypassed and labelled:
  - missed task → Freya
  - complete a task → Albedo
  - end of day → Anya
  - check-in → ZeroTwo
  - load sample history
  - reset

## Run it locally

Backend (Python 3.11+):

```bash
python -m venv .venv && . .venv/bin/activate
pip install ".[dev]"
cp .env.example .env        # add GEMINI_API_KEY to use live AI replies (optional)
uvicorn api.main:app --port 8000
```

Frontend (Node 20+):

```bash
cd frontend
npm ci
npm run dev                 # http://localhost:3000 (uses NEXT_PUBLIC_API_URL, default http://localhost:8000)
```

Without a Gemini key, the planner, tracking and analytics all work, and the Council answers with labelled sample replies. For full local use (live nudges on a timer), set `ENABLE_PROACTIVE_LLM=true`. To try the evaluator experience locally, set `DEMO_MODE=true`.

## How to evaluate

- `python -m pytest`: unit and API tests (temporary databases, no AI calls).
- `python -m scripts.smoke_test`: end-to-end check on a throwaway database. It reports PASS/FAIL/SKIP honestly.
- `evals/EVALS.md`: every test that was run, with real output and evidence (`evals/evidence/`), plus what is still unverified.
- `prompts/PROMPTS.md`: the persona/system prompts and the prompts used to improve this project.

## Known limits

- **Self-reported, not measured.** Scores reflect what you mark. The workload signal is a heuristic.
- **Personas untested against a live model.** Their prompts have only been checked statically (see `evals/EVALS.md`).
- **No accounts.** Outside demo mode there is one local SQLite database. In demo mode, data is per browser session and temporary.
- **AI uses Google's Gemini API.** Free-tier content may be used by Google to improve its products, so don't enter personal information.

## Project layout

```text
agents/         persona YAML, agent runtime, orchestrator
analytics/      metrics, trends, analytics pipeline
api/            FastAPI app and routers
config/         settings (env vars)
core/           models and exceptions
data/           SQLite access and migrations
events/         event bus and rules
memory/         short-term and long-term memory
notifications/  scheduler and event emitters
tools/          tools the agents may call
frontend/       Next.js app
```
