"""
Integration fixtures: run the FastAPI app against a fresh temporary SQLite file.

The app lifespan (scheduler, agent runtimes) is NOT started here; tests exercise
the REST layer + repositories + analytics pipeline only. No LLM calls are made.
"""

import asyncio

import httpx
import pytest

from data.database import db


@pytest.fixture
async def client(tmp_path):
    db._db_path = tmp_path / "test.db"
    db._initialized = False
    db._lock = asyncio.Lock()
    await db.initialize()

    from api.main import app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    db._initialized = False
