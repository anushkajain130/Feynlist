"""
Clock
=====
"today" and "now" for the current request. Uses the browser's time zone when the
request carried one (X-Feynlist-TZ), else APP_TIMEZONE, else the server's local
time. Returns naive values in that zone, matching how task times are stored.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config.settings import settings
from core.session import current_timezone


def _zone() -> ZoneInfo | None:
    name = current_timezone.get() or settings.app_timezone
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def is_valid_timezone(name: str | None) -> bool:
    if not name or len(name) > 64:
        return False
    try:
        ZoneInfo(name)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def now() -> datetime:
    zone = _zone()
    if zone is None:
        return datetime.now()
    return datetime.now(zone).replace(tzinfo=None)


def today() -> date:
    return now().date()
