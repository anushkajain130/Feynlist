"""
Database Connection Manager
============================
Async SQLite manager using aiosqlite.
Handles connection lifecycle, migrations, and provides a
clean context-manager interface for repositories.

Usage:
    from data.database import db

    async with db.connection() as conn:
        rows = await conn.execute("SELECT * FROM tasks WHERE date = ?", (today,))
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import aiosqlite
from loguru import logger

from config.settings import settings, PROJECT_ROOT
from core.exceptions import DatabaseError, MigrationError

# Path to migrations directory
MIGRATIONS_DIR = PROJECT_ROOT / "data" / "migrations"


class Database:
    """
    Singleton async database manager.
    Call db.initialize() once at startup.
    Use db.connection() as a context manager for all queries.
    """

    def __init__(self):
        self._db_path: Path = settings.database_path
        self._lock = asyncio.Lock()
        self._initialized = False

    def is_initialized(self) -> bool:
        """True once migrations have run (used by /health)."""
        return self._initialized

    async def initialize(self) -> None:
        """
        Must be called once at application startup.
        Creates database file, runs all pending migrations.
        """
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            # Ensure parent directory exists
            self._db_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Initializing database at: {self._db_path}")

            try:
                await self._run_migrations()
                
                # Dynamic upgrade: Add input_tokens, output_tokens, model_used, debug columns if missing
                async with aiosqlite.connect(self._db_path) as conn:
                    for col, col_type in [("input_tokens", "INTEGER DEFAULT 0"), 
                                          ("output_tokens", "INTEGER DEFAULT 0"), 
                                          ("model_used", "TEXT DEFAULT ''"), 
                                          ("debug", "TEXT")]:
                        try:
                            await conn.execute(f"ALTER TABLE agent_messages ADD COLUMN {col} {col_type}")
                        except aiosqlite.OperationalError:
                            pass # Column already exists
                    
                    try:
                        await conn.execute("ALTER TABLE daily_analytics ADD COLUMN relapsed INTEGER DEFAULT 0")
                    except aiosqlite.OperationalError:
                        pass # Column already exists
                        
                    await conn.commit()

                self._initialized = True
                logger.info("Database initialized successfully.")
            except Exception as e:
                raise MigrationError(f"Database initialization failed: {e}") from e

    async def _run_migrations(self) -> None:
        """Applies all SQL migration files in order."""
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row

            # Enable WAL mode for better concurrent performance
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA foreign_keys=ON")

            # Get current schema version
            try:
                async with conn.execute(
                    "SELECT MAX(version) as v FROM schema_version"
                ) as cursor:
                    row = await cursor.fetchone()
                    current_version = row["v"] if row and row["v"] else 0
            except aiosqlite.OperationalError:
                # schema_version table doesn't exist yet
                current_version = 0

            logger.debug(f"Current schema version: {current_version}")

            # Find and apply pending migrations
            migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
            for migration_file in migration_files:
                version = int(migration_file.stem.split("_")[0])
                if version <= current_version:
                    continue

                logger.info(f"Applying migration: {migration_file.name}")
                sql = migration_file.read_text(encoding="utf-8")

                try:
                    await conn.executescript(sql)
                    await conn.commit()
                    logger.info(f"Migration {version} applied successfully.")
                except aiosqlite.Error as e:
                    raise MigrationError(
                        f"Failed to apply migration {migration_file.name}: {e}"
                    ) from e

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """
        Async context manager for database connections.

        Example:
            async with db.connection() as conn:
                await conn.execute("INSERT INTO tasks ...")
        """
        if not self._initialized:
            await self.initialize()

        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA foreign_keys=ON")
            try:
                yield conn
            except aiosqlite.Error as e:
                await conn.rollback()
                raise DatabaseError(f"Database operation failed: {e}") from e

    async def execute_write(self, sql: str, params: tuple = ()) -> int:
        """
        Execute a single write query (INSERT/UPDATE/DELETE).
        Returns lastrowid.
        """
        async with self.connection() as conn:
            async with conn.execute(sql, params) as cursor:
                await conn.commit()
                return cursor.lastrowid

    async def fetch_one(
        self, sql: str, params: tuple = ()
    ) -> aiosqlite.Row | None:
        """Fetch a single row."""
        async with self.connection() as conn:
            async with conn.execute(sql, params) as cursor:
                return await cursor.fetchone()

    async def fetch_all(
        self, sql: str, params: tuple = ()
    ) -> list[aiosqlite.Row]:
        """Fetch all matching rows."""
        async with self.connection() as conn:
            async with conn.execute(sql, params) as cursor:
                return await cursor.fetchall()

    async def health_check(self) -> bool:
        """Returns True if the database is accessible and migrations are current."""
        try:
            row = await self.fetch_one("SELECT MAX(version) as v FROM schema_version")
            return row is not None
        except Exception:
            return False


# ---------------------------------------------------------------------------
# JSON helpers for columns stored as JSON strings
# ---------------------------------------------------------------------------

def row_to_dict(row: aiosqlite.Row) -> dict:
    """Convert an aiosqlite.Row to a plain dict."""
    return dict(row)


def parse_json_field(value: str | None, default=None):
    """Safely parse a JSON-encoded field from the database."""
    if value is None:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def dump_json_field(value) -> str:
    """Serialize a value to a JSON string for database storage."""
    return json.dumps(value, default=str)


# ---------------------------------------------------------------------------
# Singleton instance — import this everywhere
# ---------------------------------------------------------------------------
db = Database()
