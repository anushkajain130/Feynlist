"""
Free-tier AI budget
===================
Decides, before every model call, whether a *live* reply is allowed. If not,
the coach answers with a labelled pre-written sample reply instead (see
agents/sample_replies.py). Rules (CLAUDE.md, "Free-tier AI budget"):

  - LIVE_REPLIES_PER_SESSION live replies per evaluator session (default 2).
    Chat messages and demo-control nudges count together.
  - LIVE_AI_DAILY_CAP live model requests per day across everyone (reset at
    midnight Pacific, like Gemini's free-tier daily quota). The owner sets it
    below their AI Studio daily limit, leaving headroom.
  - LIVE_AI_PER_MINUTE requests per rolling minute (simple guard for the
    per-minute limit); over it -> sample reply with "try again in a moment".

Counters are stored server-side in a small SQLite file (AI_BUDGET_PATH),
separate from session data, so "Reset demo" does not refill them. On hosts with
ephemeral disks a restart resets them; Google's own quota (-> 429 -> sample
reply) remains the final backstop.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config.settings import settings

PACIFIC = ZoneInfo("America/Los_Angeles")

# Why a reply is a sample (shown to the user next to the "Sample reply" label).
SAMPLE_REASONS = {
    "session_limit": "You've used this session's live replies, so this is a pre-written sample reply.",
    "daily_cap": "Today's live-reply budget for the demo is used up, so this is a pre-written sample reply.",
    "rate_limit": "Lots of requests right now: try again in a moment for a live reply. Here's a pre-written sample.",
    "quota": "The free AI quota is used up right now, so this is a pre-written sample reply.",
    "provider_error": "The AI service didn't respond, so this is a pre-written sample reply.",
    "no_api_key": "Live AI isn't set up on this server, so this is a pre-written sample reply.",
    "council_demo": "The all-five Council isn't live in the public demo (it would use five requests at once), so these are pre-written samples.",
    "proactive_off": "Automatic nudges use pre-written samples in the public demo to save the free AI quota.",
}


@dataclass
class Decision:
    live: bool
    reason: str | None = None   # key of SAMPLE_REASONS when live is False


class AIBudget:
    def __init__(self):
        self._lock = threading.Lock()
        self._minute: deque[float] = deque()
        self._conn: sqlite3.Connection | None = None
        self._path: Path | None = None

    # ---- storage -----------------------------------------------------------
    def _db(self) -> sqlite3.Connection:
        path = Path(settings.ai_budget_path)
        if self._conn is None or self._path != path:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(path, check_same_thread=False)
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS counters (key TEXT PRIMARY KEY, n INTEGER NOT NULL)")
            self._path = path
        return self._conn

    def _get(self, key: str) -> int:
        row = self._db().execute("SELECT n FROM counters WHERE key = ?", (key,)).fetchone()
        return row[0] if row else 0

    def _add(self, key: str, delta: int) -> None:
        db = self._db()
        db.execute("INSERT INTO counters(key, n) VALUES (?, ?) "
                   "ON CONFLICT(key) DO UPDATE SET n = MAX(0, n + excluded.n)", (key, delta))
        db.commit()

    @staticmethod
    def _day_key() -> str:
        return "day:" + datetime.now(PACIFIC).date().isoformat()

    # ---- policy ------------------------------------------------------------
    def session_limit(self) -> int | None:
        """Per-session live replies; None = unlimited (single-user mode)."""
        from core.session import current_session_id
        if current_session_id.get() is None:
            return None
        return settings.live_replies_per_session

    def status(self) -> dict:
        from core.session import current_session_id
        sid = current_session_id.get()
        with self._lock:
            used_today = self._get(self._day_key())
            used_session = self._get(f"session:{sid}") if sid else 0
        limit = self.session_limit()
        cap = settings.live_ai_daily_cap
        left = None if limit is None else max(0, limit - used_session)
        cap_reached = cap > 0 and used_today >= cap
        live_possible = settings.has_api_key and not cap_reached and (left is None or left > 0)
        return {
            "ai_configured": settings.has_api_key,
            "live_limit": limit,
            "live_left": left,
            "daily_cap_reached": cap_reached,
            "mode": "live" if live_possible else "sample",
            "council_live": not settings.demo_mode,
        }

    def reserve(self) -> Decision:
        """Call right before a model request. Counts it if allowed."""
        from core.session import current_session_id
        if not settings.has_api_key:
            return Decision(False, "no_api_key")
        sid = current_session_id.get()
        now = time.time()
        with self._lock:
            limit = self.session_limit()
            if limit is not None and self._get(f"session:{sid}") >= limit:
                return Decision(False, "session_limit")
            cap = settings.live_ai_daily_cap
            if cap > 0 and self._get(self._day_key()) >= cap:
                return Decision(False, "daily_cap")
            while self._minute and now - self._minute[0] > 60:
                self._minute.popleft()
            if settings.live_ai_per_minute > 0 and len(self._minute) >= settings.live_ai_per_minute:
                return Decision(False, "rate_limit")
            self._minute.append(now)
            self._add(self._day_key(), 1)
            if sid:
                self._add(f"session:{sid}", 1)
        return Decision(True)

    def refund_session(self) -> None:
        """The request failed, so it didn't produce a live reply: give the session its reply back.
        (The daily request count is not refunded; Google counted the request.)"""
        from core.session import current_session_id
        sid = current_session_id.get()
        if sid:
            with self._lock:
                self._add(f"session:{sid}", -1)


ai_budget = AIBudget()
