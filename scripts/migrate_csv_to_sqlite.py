"""
CSV → SQLite Migration Script
==============================
Migrates all legacy Feynlist CSV data into the new SQLite database.

Usage:
    python scripts/migrate_csv_to_sqlite.py

What it migrates:
  1. FL_task_master.csv  → tasks table (historical archive)
  2. FL_tasks_daily.csv  → tasks table (today's data, overwrites master for today)
  3. FL_analytics_master.csv → daily_analytics table

Data cleaning applied:
  - Fixes malformed dates (e.g. '2-12-30', '2O25-01-11')
  - Deduplicates rows by (date, task, start_time)
  - Fills missing numeric values with 0
  - Maps old column names to new schema
  - Generates proper task IDs (sha256 hash)
  - Skips empty rows silently
"""

import asyncio
import hashlib
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger

# Make project root importable
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from core.models import Task, TaskClass, DailyMetrics
from data.database import db
from data.repositories.task_repo import task_repo
from data.repositories.analytics_repo import analytics_repo

# ─── Paths to legacy CSV files ───────────────────────────────────────────────
LEGACY_DIR = Path("d:/feynlist backup")
TASK_MASTER_CSV = LEGACY_DIR / "FL_task_master.csv"
TASKS_DAILY_CSV = LEGACY_DIR / "FL_tasks_daily.csv"
ANALYTICS_CSV   = LEGACY_DIR / "FL_analytics_master.csv"


# =============================================================================
# DATE CLEANING
# =============================================================================

DATE_FIXES = {
    # Known malformed dates found in FL_task_master.csv
    "2-12-30":   "2024-12-30",
    "2-16":      "2025-01-16",
    "2-11":      "2025-01-11",
    "2O25-01-11": "2025-01-11",
    "2025-1-":   None,   # Unfixable — skip
}

def clean_date(raw: str) -> Optional[date]:
    """
    Attempt to parse a date string, applying known fixes.
    Returns None for unfixable / empty strings.
    """
    if not raw or str(raw).strip() in ("", "nan", "NaT"):
        return None

    raw = str(raw).strip()

    # Apply known fixes first
    if raw in DATE_FIXES:
        fixed = DATE_FIXES[raw]
        if fixed is None:
            return None
        raw = fixed

    # Replace letter O with zero (typo)
    raw = raw.replace("O", "0").replace("o", "0")

    # Try ISO format YYYY-MM-DD
    try:
        return date.fromisoformat(raw)
    except ValueError:
        pass

    # Try DD-MM-YYYY
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass

    logger.warning(f"Could not parse date: '{raw}' — skipping row")
    return None


# =============================================================================
# TASK ID GENERATION
# =============================================================================

def make_task_id(task_date: date, task_name: str, start_time: str) -> str:
    raw = f"{task_date.isoformat()}|{task_name.strip()}|{start_time.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# =============================================================================
# TASK CLASS NORMALIZATION
# =============================================================================

CLASS_ALIASES = {
    "yoga and wellness": "Yoga_and_Wellness",
    "yoga_and_wellness": "Yoga_and_Wellness",
    "academics_selfstudy": "Academics_Selfstudy",
    "academic_classes": "Academic_Classes",
    "book reading": "Book_Reading",
    "book_reading": "Book_Reading",
    "side_business": "Side_Business",
    "extraacti": "ExtraActi",
    "level_up": "level_up",
    "level_down": "level_down",
    "deviated": "Deviated",
    "revived": "revived",
}

def normalize_class(raw: str) -> TaskClass:
    if not raw or str(raw).strip() in ("", "nan"):
        return TaskClass.UNSPECIFIED
    cleaned = str(raw).strip()
    alias = CLASS_ALIASES.get(cleaned.lower(), cleaned)
    return TaskClass(alias)


# =============================================================================
# BOOL CLEANING
# =============================================================================

def clean_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes")
    return False


# =============================================================================
# TIME CLEANING
# =============================================================================

def clean_time(val: str) -> str:
    """Normalize time to HH:MM format."""
    if not val or str(val).strip() in ("", "nan"):
        return "00:00"
    val = str(val).strip()
    if re.match(r"^\d{1,2}:\d{2}$", val):
        h, m = val.split(":")
        return f"{int(h):02d}:{int(m):02d}"
    return val[:5]  # Truncate if longer


# =============================================================================
# MIGRATION: TASKS
# =============================================================================

async def migrate_tasks(csv_path: Path, label: str) -> int:
    """
    Migrate tasks from a CSV file into the tasks table.
    Returns number of rows successfully migrated.
    """
    if not csv_path.exists():
        logger.warning(f"{label}: File not found at {csv_path} — skipping.")
        return 0

    logger.info(f"Reading {label}: {csv_path}")
    df = pd.read_csv(csv_path, dtype=str)
    df = df.fillna("")

    logger.info(f"{label}: {len(df)} raw rows")

    tasks_to_upsert: list[Task] = []
    skipped = 0
    seen_ids: set[str] = set()

    for idx, row in df.iterrows():
        # Parse date
        task_date = clean_date(row.get("Date", ""))
        if task_date is None:
            skipped += 1
            continue

        # Parse required fields
        task_name = str(row.get("Task", "")).strip()
        if not task_name:
            skipped += 1
            continue

        start_time = clean_time(row.get("StartTime", "00:00"))
        end_time   = clean_time(row.get("Endtime", "00:00"))

        # Generate ID and deduplicate
        task_id = make_task_id(task_date, task_name, start_time)
        if task_id in seen_ids:
            skipped += 1
            continue
        seen_ids.add(task_id)

        # Parse numeric fields
        try:
            points = int(float(row.get("Points", 0) or 0))
        except (ValueError, TypeError):
            points = 0

        try:
            slider_val = int(float(row.get("SliderVal", 0) or 0))
        except (ValueError, TypeError):
            slider_val = 0

        try:
            ps_var = float(row.get("PS_var", 0.0) or 0.0)
        except (ValueError, TypeError):
            ps_var = 0.0

        task = Task(
            id=task_id,
            date=task_date,
            task=task_name,
            start_time=start_time,
            end_time=end_time,
            points=points,
            completed=clean_bool(row.get("Completed", False)),
            task_class=normalize_class(row.get("Class", "")),
            sub_class=str(row.get("SubClass", "")).strip() or None,
            sub_class2=str(row.get("SubClass2", "")).strip() or None,
            slider_val=slider_val,
            ps_var=ps_var,
            start_and_sit=clean_bool(row.get("Start_and_Sit_for_5_mins", False)),
            complete_task=clean_bool(row.get("Complete_the_task", False)),
            be_attentive=clean_bool(row.get("Be_attentive", False)),
        )
        tasks_to_upsert.append(task)

    if tasks_to_upsert:
        await task_repo.bulk_upsert(tasks_to_upsert)

    logger.info(
        f"{label}: migrated {len(tasks_to_upsert)} tasks, skipped {skipped} rows"
    )
    return len(tasks_to_upsert)


# =============================================================================
# MIGRATION: ANALYTICS
# =============================================================================

async def migrate_analytics() -> int:
    """
    Migrate FL_analytics_master.csv → daily_analytics table.
    Maps old column names to new schema.
    """
    if not ANALYTICS_CSV.exists():
        logger.warning(f"Analytics CSV not found at {ANALYTICS_CSV} — skipping.")
        return 0

    logger.info(f"Reading analytics CSV: {ANALYTICS_CSV}")
    df = pd.read_csv(ANALYTICS_CSV, dtype=str)
    df = df.fillna("")

    logger.info(f"Analytics CSV: {len(df)} raw rows")

    migrated = 0
    skipped = 0

    for idx, row in df.iterrows():
        target_date = clean_date(row.get("Date", ""))
        if target_date is None:
            skipped += 1
            continue

        def safe_float(val, default=0.0) -> float:
            try:
                v = float(val)
                return v if not pd.isna(v) else default
            except (ValueError, TypeError):
                return default

        def safe_int(val, default=0) -> int:
            try:
                return int(float(val)) if val != "" else default
            except (ValueError, TypeError):
                return default

        metrics = DailyMetrics(
            date=target_date,
            alertness=safe_float(row.get("Alertness", 0.0)),
            discipline=safe_float(row.get("Discipline", 0.0)),
            ps_hrs=safe_float(row.get("PS_hrs", 0.0)),
            # Old column: Aura → new: aura (keep as-is)
            aura=safe_float(row.get("Aura", 0.0)),
            retention_streak=safe_int(row.get("Reten_Streak", 0)),
            happiness=safe_float(row.get("Happiness", 0.0)),
            total_points=0,     # Not in old analytics CSV — recomputed later
            tasks_completed=0,  # Not in old analytics CSV — recomputed later
            tasks_total=0,      # Not in old analytics CSV — recomputed later
        )

        await analytics_repo.upsert_metrics(metrics)
        migrated += 1

    logger.info(
        f"Analytics: migrated {migrated} records, skipped {skipped} rows"
    )
    return migrated


# =============================================================================
# ENTRYPOINT
# =============================================================================

async def main():
    logger.info("=" * 60)
    logger.info("Feynlist CSV → SQLite Migration")
    logger.info("=" * 60)

    # Initialize database (runs migrations, creates tables)
    await db.initialize()

    # 1. Migrate historical task archive first
    await migrate_tasks(TASK_MASTER_CSV, "FL_task_master.csv")

    # 2. Migrate today's tasks (overwrites any matching master entries)
    await migrate_tasks(TASKS_DAILY_CSV, "FL_tasks_daily.csv")

    # 3. Migrate analytics
    await migrate_analytics()

    # 4. Health check
    healthy = await db.health_check()
    if healthy:
        logger.info("✅ Migration complete. Database is healthy.")
    else:
        logger.error("❌ Database health check failed after migration!")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info(f"Database location: {settings.database_path}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
