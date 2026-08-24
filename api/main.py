"""
FastAPI Application
===================
Main entry point for the Feynlist V1 API.

Run with:
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

The lifespan handler ensures clean startup and shutdown:
  - startup: DB init → tools → agents → events → scheduler
  - shutdown: scheduler stop → session consolidation
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from core.startup import startup, shutdown
from api.routers import tasks, analytics, agents
from api.schemas import HealthResponse, ErrorResponse
from notifications.scheduler import scheduler
from agents.orchestrator import orchestrator
from core.models import AgentId


# =============================================================================
# LIFESPAN
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context — startup before yield, shutdown after."""
    await startup()
    yield
    await shutdown()


# =============================================================================
# APP
# =============================================================================

app = FastAPI(
    title="Feynlist API",
    description=(
        "AI-powered productivity operating system. "
        "Task management, analytics, and The Council of five AI agents."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — allow all origins for local development
# In production, restrict to your frontend domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# ROUTERS
# =============================================================================

app.include_router(tasks.router)
app.include_router(analytics.router)
app.include_router(agents.router)


# =============================================================================
# HEALTH + ROOT
# =============================================================================

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Feynlist V1 API — see /docs"}


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """System health check. Returns DB, scheduler, and agent readiness."""
    from data.database import db
    db_ok = db.is_initialized()

    agent_status = orchestrator.agent_status()
    agents_ready = sum(1 for s in agent_status.values() if s["ready"])

    status = "healthy" if db_ok and scheduler.is_running() else "degraded"

    return HealthResponse(
        status=status,
        db_ok=db_ok,
        scheduler_running=scheduler.is_running(),
        agents_ready=agents_ready,
    )


# =============================================================================
# GLOBAL ERROR HANDLER
# =============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc),
            code=500,
        ).model_dump(),
    )
