# Deploying Feynlist (about 20 minutes)

You will put the **backend on Render** (free) and the **frontend on Vercel** (free). Your Gemini key is typed into Render only, never into the code or a chat.

## What you need

| Thing | Where | Notes |
|---|---|---|
| GitHub account | already have | The repo must contain the deploy files on the branch you deploy (see step 0) |
| Render account | <https://render.com> → **Get Started** → **Sign in with GitHub** | Free plan; no card needed for a free web service |
| Vercel account | already have | Sign in with GitHub |
| Gemini API key (free) | <https://aistudio.google.com/apikey> → **Create API key** | Optional: without it the app works and the coaches give labelled sample replies |
| Your free daily limit | AI Studio → **Rate limits** page | Note the requests-per-day number for `gemini-2.5-flash` and `gemini-2.5-flash-lite` |

## 0. Pick the branch

The deploy files (`render.yaml`, `.python-version`, this guide) are on `claude/dazzling-hopper-tk9c3k`. Either:

- **Merge it into `main` first.** Simplest: both hosts deploy `main` by default.
- **Or** choose that branch in both dashboards below.

## 1. Backend on Render

1. Render dashboard → **New +** → **Blueprint**.
2. Connect GitHub if asked, then pick the **Feynlist** repo (and the branch from step 0). Render reads `render.yaml` and shows a service called **feynlist-api** on the **Free** plan.
3. Render asks for the two values marked "sync: false":
   - **GEMINI_API_KEY**: paste your key (or leave empty to run with sample replies only).
   - **ALLOWED_ORIGINS**: type `*` for now. You'll change it in step 3.
4. Click **Apply** / **Deploy Blueprint**. The first build takes about 3–5 minutes. Wait for **Live**.
5. Copy the service URL from the top of the page, e.g. `https://feynlist-api.onrender.com`.
6. Check it: open `https://<your-render-url>/health` in a browser. You should see `"status":"healthy"`.

Before going public, set **LIVE_AI_DAILY_CAP** (Render → feynlist-api → **Environment**) to a number below your AI Studio requests-per-day, leaving room for your own tests. It is 20 by default. If one of the two models has a much higher free daily limit, you can set both `GEMINI_MODEL_STANDARD` and `GEMINI_MODEL_LIGHT` to that model.

## 2. Frontend on Vercel

1. Vercel dashboard → **Add New…** → **Project** → import the **Feynlist** repo.
2. **Root Directory**: click **Edit** and choose `frontend`. Framework is detected as **Next.js**.
3. **Environment Variables**: add
   - Name `NEXT_PUBLIC_API_URL`, Value `https://<your-render-url>`, with no trailing slash.

   This must be set **before** the build. If you add or change it later, redeploy (Deployments → ⋯ → **Redeploy**).
4. If you didn't merge into `main`, set the production branch under **Settings → Git**.
5. Click **Deploy**. Copy the site URL, e.g. `https://feynlist.vercel.app`.

## 3. Lock the backend to your site

Render → feynlist-api → **Environment** → set **ALLOWED_ORIGINS** to your Vercel URL exactly, e.g. `https://feynlist.vercel.app` (no trailing slash; comma-separate if you have more than one). Save. Render redeploys by itself (about 1–2 minutes).

## 4. Check it

- **In a private browser window:**
  1. Open your Vercel URL. You may see "Waking the server, this can take up to a minute…" first.
  2. Then the dashboard appears with the **Demo mode · Sample data** panel.
  3. Try a demo control, then message a coach on the Council page.
- **On your phone:** open the same URL.
- **Scripted check** (or ask Claude Code to run it):

```bash
python -m scripts.check_deploy --api https://<your-render-url> --web https://<your-vercel-url>
```

It runs the evaluator journey on a fresh session: health, sample data, a task toggle updating analytics, one coach reply, CORS and the websocket over `wss`. It prints PASS/FAIL. It uses **one** live reply if quota allows.

## Good to know

- **Free Render services sleep** after 15 minutes without traffic and take about a minute to wake. **Open the app once shortly before you submit** or share the link.
- **Demo data is temporary** (`/tmp`). A restart or redeploy wipes all demo sessions and the live-reply counters. That's expected; new visitors get fresh sample data.
- **Your key** lives only in Render's Environment page. To rotate it, edit `GEMINI_API_KEY` there.
- **Live AI budget:** 2 live replies per browser session, plus `LIVE_AI_DAILY_CAP` across everyone. Everything else is a labelled sample reply. Scheduled AI calls are off (`ENABLE_PROACTIVE_LLM=false`).
- **Alternatives** if Render's free plan doesn't suit you: Railway or Fly.io. Both run the same start command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`, with Python 3.12 and the same environment variables.

All variables are described in `.env.example`.
