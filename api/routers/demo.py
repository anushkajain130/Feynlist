"""
Demo Router
===========
GET  /api/demo/status        — is demo mode on, and is this session's history sample data
POST /api/demo/reset         — wipe this session and start again from the sample data
POST /api/demo/load-sample   — replace the last 14 days with sample history (keeps today)

Only available when DEMO_MODE=true (every call then belongs to one evaluator session).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from config.settings import settings
from core.session import current_session_id

router = APIRouter(prefix="/api/demo", tags=["Demo"])


def _require_demo() -> str:
    sid = current_session_id.get()
    if not settings.demo_mode or sid is None:
        raise HTTPException(status_code=404, detail="Demo mode is off on this server.")
    return sid


@router.get("/status")
async def demo_status():
    from core.clock import today
    return {
        "demo_mode": settings.demo_mode,
        "sample_data": settings.demo_mode,
        "today": today().isoformat(),
        "notice": (
            "Demo mode: this session uses sample data (about two weeks of made-up history). "
            "It is stored in temporary storage and may reset when the server restarts."
        ) if settings.demo_mode else None,
    }


@router.post("/reset")
async def reset_demo():
    """Delete this session's data and agent state, then re-seed the sample data."""
    from agents.orchestrator import drop_session_orchestrator
    from api.session_middleware import ensure_session_ready
    from data.database import session_databases

    sid = _require_demo()
    drop_session_orchestrator(sid)
    session_databases.drop(sid)
    await ensure_session_ready(sid, force_reseed=True)
    return {"reset": True}


@router.post("/load-sample")
async def load_sample_history():
    """Replace the last 14 days with sample history; today's plan is kept."""
    from analytics.pipeline import pipeline
    from core.clock import today
    from demo.sample_data import HISTORY_DAYS, seed_history

    _require_demo()
    await seed_history()
    await pipeline.run(today())  # today's streak builds on the new history
    return {"loaded_days": HISTORY_DAYS}


# -----------------------------------------------------------------------------
# Demo controls: fire the same events the scheduler / task API fire, right now.
# Cooldowns are bypassed for these calls only (the UI labels this "demo mode").
# -----------------------------------------------------------------------------

TRIGGERS = {
    "missed-task": "Freya calls out a missed task",
    "complete-task": "Albedo celebrates a completed task",
    "end-of-day": "Anya reviews the day (plus workload and streak checks)",
    "check-in": "ZeroTwo's scheduled check-in",
}


@router.post("/trigger/{kind}")
async def demo_trigger(kind: str):
    from api.routers.agents import ws_payload
    from analytics.pipeline import pipeline
    from core.clock import now, today
    from core.session import bypass_cooldowns, proactive_sink
    from data.repositories.task_repo import task_repo
    from notifications import triggers

    _require_demo()
    if kind not in TRIGGERS:
        raise HTTPException(status_code=404, detail=f"Unknown demo control '{kind}'.")

    sink: list = []
    sink_token = proactive_sink.set(sink)
    bypass_token = bypass_cooldowns.set(True)
    detail = ""
    try:
        tasks = sorted(await task_repo.get_tasks_for_date(today()), key=lambda t: t.start_time)
        open_tasks = [t for t in tasks if not t.completed and t.task_class.value not in ("Sleep", "Break")]

        if kind == "missed-task":
            current = now().time()
            missed = [t for t in open_tasks if t.is_past_at(current)] or open_tasks
            if not missed:
                return {"kind": kind, "messages": [], "detail": "Every task today is done, so nothing can be missed."}
            await triggers.emit_task_missed_for(missed[0], source="demo")
            detail = f"Marked '{missed[0].task}' as missed."

        elif kind == "complete-task":
            if not open_tasks:
                return {"kind": kind, "messages": [], "detail": "Every task today is already done."}
            task = open_tasks[0]
            done = await task_repo.toggle_complete(task_id=task.id, completed=True, slider_val=85)
            await pipeline.run(done.date)
            await triggers.emit_task_completed(done)
            detail = f"Completed '{done.task}'."

        elif kind == "end-of-day":
            await triggers.emit_day_end()
            detail = "Ran the end-of-day review, workload check and streak check."

        elif kind == "check-in":
            await triggers.emit_scheduled_checkin()
            detail = "Ran ZeroTwo's scheduled check-in."
    finally:
        bypass_cooldowns.reset(bypass_token)
        proactive_sink.reset(sink_token)

    return {
        "kind": kind,
        "detail": detail,
        "cooldowns_bypassed": True,
        "messages": [ws_payload(m, proactive=True) for m in sink],
    }
