"""
API Request/Response Schemas
=============================
Pydantic models for all FastAPI endpoints.
Separate from domain models — these are the API contract, not the DB contract.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# =============================================================================
# TASKS
# =============================================================================

class TaskResponse(BaseModel):
    id: str
    date: str
    task: str
    start_time: str
    end_time: str
    points: int
    completed: bool
    task_class: str
    sub_class: Optional[str]
    sub_class2: Optional[str]
    start_and_sit: bool
    complete_task: bool
    be_attentive: bool
    slider_val: int
    ps_var: float


class TaskListResponse(BaseModel):
    date: str
    tasks: list[TaskResponse]
    total: int
    completed: int
    completion_pct: float


class ToggleSubtaskRequest(BaseModel):
    task_id: str = Field(description="Task UUID")
    subtask_name: str = Field(
        description="One of: Start_and_Sit_for_5_mins, Complete_the_task, Be_attentive"
    )
    value: bool
    slider_val: Optional[int] = None


class ToggleSubtaskResponse(BaseModel):
    success: bool
    task: TaskResponse


class ToggleCompleteRequest(BaseModel):
    task_id: str = Field(description="Task UUID")
    completed: bool
    slider_val: int = 100


class ToggleCompleteResponse(BaseModel):
    success: bool
    task: TaskResponse


class ScheduleItemIn(BaseModel):
    """One task in a schedule submission."""
    name: str = Field(description="Task name / description")
    start_time: str = Field(description="HH:MM format")
    end_time: str = Field(description="HH:MM format")
    task_class: str = Field(default="Unspecified", description="TaskClass enum value")
    sub_class: Optional[str] = None


class ScheduleRequest(BaseModel):
    """Bulk schedule submission for one day."""
    date: Optional[str] = Field(default=None, description="YYYY-MM-DD. Defaults to today.")
    tasks: list[ScheduleItemIn]



# =============================================================================
# ANALYTICS
# =============================================================================

class DailyMetricsResponse(BaseModel):
    date: str
    alertness: float
    discipline: float
    ps_hrs: float
    aura: float
    retention_streak: int
    total_points: int
    tasks_completed: int
    tasks_total: int
    completion_rate: float
    has_data: bool
    # Daily check-in: null = not answered, true = kept commitment, false = "not today"
    kept_commitment: Optional[bool] = None


class CheckInRequest(BaseModel):
    """Neutral daily consistency check-in."""
    date: Optional[str] = None  # YYYY-MM-DD, defaults to today
    kept_commitment: bool = Field(
        description="True = 'I kept my commitment today', False = 'Not today'"
    )


class TrendResponse(BaseModel):
    metric: str
    direction: str          # improving / declining / stable
    data_points: list[dict] # [{date, value}]
    avg_7day: float


class WeeklySummaryResponse(BaseModel):
    week_start: str
    avg_discipline: float
    avg_alertness: float
    total_ps_hrs: float
    avg_aura: float
    best_day: Optional[str]
    worst_day: Optional[str]
    streak_delta: int


class BurnoutSignalResponse(BaseModel):
    detected: bool
    severity: str
    factors: list[str]
    recommendation: str


# =============================================================================
# AGENTS
# =============================================================================

class SendMessageRequest(BaseModel):
    message: str = Field(description="User's message text")
    agent_id: Optional[str] = Field(
        default=None,
        description="Target agent ID. If null, orchestrator picks the best agent."
    )
    bypass_cooldown: bool = Field(
        default=False,
        description="Skip cooldown check (admin only in production)"
    )


class AgentMessageResponse(BaseModel):
    id: str
    agent_id: str
    display_name: str
    content: str
    timestamp: str
    triggered_by: Optional[str]
    tool_used: Optional[str]
    input_tokens: int = 0
    output_tokens: int = 0
    tokens_used: int = 0
    model_used: str = ""
    latency_ms: int = 0
    debug: Optional[dict] = None


class CouncilResponse(BaseModel):
    messages: list[AgentMessageResponse]
    total_agents: int


class AgentStatusResponse(BaseModel):
    agents: dict[str, dict]   # {agent_id: {ready, seconds_until_ready}}


# =============================================================================
# MEMORY
# =============================================================================

class StoreMemoryRequest(BaseModel):
    content: str
    memory_type: str = "factual"
    tags: list[str] = []
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    shared: bool = True


class MemoryResponse(BaseModel):
    id: str
    agent_id: Optional[str]
    memory_type: str
    content: str
    tags: list[str]
    importance: float
    created_at: str


class MemorySearchResponse(BaseModel):
    memories: list[MemoryResponse]
    total: int


# =============================================================================
# SYSTEM
# =============================================================================

class HealthResponse(BaseModel):
    status: str             # "healthy" or "degraded"
    db_ok: bool
    scheduler_running: bool
    agents_ready: int
    version: str = "1.0.0"


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: int
