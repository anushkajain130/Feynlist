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
