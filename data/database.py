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

    def __init__(self, db_path: Path | None = None):
        self._db_path: Path = db_path or settings.database_path
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
# Per-session databases (demo mode)
# ---------------------------------------------------------------------------

class SessionDatabases:
    """
    One SQLite file per evaluator session, under DEMO_DATA_DIR (ephemeral storage
    is fine: sessions are throwaway). Least-recently-used sessions beyond
    DEMO_MAX_SESSIONS are evicted and their files deleted.
    """

    def __init__(self):
        from collections import OrderedDict
        self._dbs: "OrderedDict[str, Database]" = OrderedDict()

    def path_for(self, session_id: str) -> Path:
        return Path(settings.demo_data_dir) / f"session-{session_id}.db"

    def get(self, session_id: str) -> tuple[Database, bool]:
        """Return (database, created_now)."""
        if session_id in self._dbs:
            self._dbs.move_to_end(session_id)
            return self._dbs[session_id], False
        database = Database(self.path_for(session_id))
        existed = database._db_path.exists()
        self._dbs[session_id] = database
        self._evict()
        return database, not existed

    def drop(self, session_id: str) -> None:
        """Forget a session and delete its database files."""
        self._dbs.pop(session_id, None)
        base = self.path_for(session_id)
        for suffix in ("", "-wal", "-shm"):
            Path(str(base) + suffix).unlink(missing_ok=True)

    def _evict(self) -> None:
        while len(self._dbs) > settings.demo_max_sessions:
            old_id, _ = self._dbs.popitem(last=False)
            self.drop(old_id)
            logger.info(f"SessionDatabases: evicted session {old_id[:8]}…")

    def __len__(self) -> int:
        return len(self._dbs)


session_databases = SessionDatabases()

# The database used outside demo sessions (local single-user mode, scheduler, scripts).
default_db = Database()


class _DatabaseProxy:
    """
    `db` used by every repository. Resolves to the current request's session
    database when a demo session is active, otherwise to `default_db`.
    """

    def _target(self) -> Database:
        from core.session import current_session_id
        sid = current_session_id.get()
        if sid is None:
            return default_db
        return session_databases.get(sid)[0]

    def __getattr__(self, name):
        return getattr(self._target(), name)

    def __setattr__(self, name, value):
        setattr(self._target(), name, value)


# Import this everywhere
db = _DatabaseProxy()
