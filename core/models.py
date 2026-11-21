"""
Core Domain Models
==================
All Pydantic v2 models for the Feynlist domain.
These are the canonical data shapes used everywhere in the system.
No database-specific logic here — pure domain objects.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, time
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, computed_field, model_validator


# =============================================================================
# ENUMS
# =============================================================================


class TaskClass(str, Enum):
    """All valid task classification categories."""

    UNSPECIFIED = "Unspecified"
    YOGA_AND_WELLNESS = "Yoga_and_Wellness"
    BREAK = "Break"
    ACADEMICS_SELFSTUDY = "Academics_Selfstudy"
    ACADEMIC_CLASSES = "Academic_Classes"
    BOOK_READING = "Book_Reading"
    SIDE_BUSINESS = "Side_Business"
    SLEEP = "Sleep"
    EXTRA_ACTI = "ExtraActi"
    SOCIAL = "Social"
    PROJECT = "Project"
    DEVIATED = "Deviated"
    SELF_GROWTH = "Self_Growth"
    WORK = "Work"
    LEVEL_UP = "level_up"
    LEVEL_DOWN = "level_down"
    REVIVED = "revived"

    @classmethod
    def _missing_(cls, value: object) -> "TaskClass":
        """Gracefully handle unknown class names from legacy data."""
        return cls.UNSPECIFIED


class DeviatedSubClass(str, Enum):
    """Specific sub-classifications for Deviated tasks."""

    PHONE_URGE = "D_by_phone_urge"
    ALARM_FAIL_MIDDAY = "D_by_alarm_fail_midday"
    FAMILY_OBJ = "D_by_family_obj"
    ALARM_FAIL_STARTDAY = "D_by_alarm_fail_startday"
    RESISTANCE_TO_TASK = "D_by_resistance_to_task"
    LACK_TIME_AWARENESS = "D_by_lack_time_awareness"
    MEANINGLESS_INDISCIPLINE = "D_by_meaningless_indicipline"
    UNPLANNED_SLEEP_EXHAUSTED = "D_by_unplanned_sleep_exhausted"
    UNPLANNED_FL = "D_by_unplanned_FL"
    TAMAS_OVERLOAD = "D_by_Tamas_overload"
    EXTREME_UNEASE = "D_by_extreme_unease"
    NO_ENERGY = "DE_by_no_energy"
    SADNESS_OF_INACTIVITY = "DE_by_sadness_of_inactivity"
    FEAR_OF_FAILURE = "DE_by_fear_of_failure"
    FEAR_OF_FAILURE_CONFRONTATION = "DE_by_fear_of_failure_confrontation"


class RevivedSubClass(str, Enum):
    """Sub-classifications for Revived tasks."""

    PHONE_LOCK = "R_Phone_lock"
    EGO = "R_Ego"
    SLEEPING_POSTURE = "R_Sleeping_posture"
    BRAIN_CONDITIONING = "R_Brain_conditioning"


class UserTier(str, Enum):
    """Subscription tier for the user."""

    FREE = "free"
    PRO = "pro"
    ULTRA = "ultra"
    ENTERPRISE = "enterprise"


class EventType(str, Enum):
    """All event types that flow through the event bus."""

    # Task lifecycle
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_MISSED = "task_missed"
    SUBTASK_TOGGLED = "subtask_toggled"
    TASK_ADDED = "task_added"

    # Behavioral signals
    INACTIVITY_DETECTED = "inactivity_detected"
    DISTRACTION_DETECTED = "distraction_detected"
    PRODUCTIVITY_SPIKE = "productivity_spike"
    FOCUS_DROP = "focus_drop"
    LOW_ENERGY_DETECTED = "low_energy_detected"
    CONSECUTIVE_MISSES = "consecutive_misses"
    SOCIAL_OVERRUN = "social_overrun"
    DEVIATED_CLASS_LOGGED = "deviated_class_logged"
    REVIVED_CLASS_LOGGED = "revived_class_logged"
    BURNOUT_DETECTED = "burnout_detected"
    HIGH_SCORE = "high_score"
    PERFORMANCE_DROP = "performance_drop"

    # Streak events
    STREAK_BROKEN = "streak_broken"
    STREAK_MILESTONE = "streak_milestone"

    # Day lifecycle
    DAY_START = "day_start"
    DAY_STARTED = "day_started"
    DAY_ENDED = "day_ended"
    DAY_END_REVIEW = "day_end_review"
    WORK_BLOCK_STARTED = "work_block_started"
    WORK_BLOCK_ENDED = "work_block_ended"
    WEEK_REVIEW = "week_review"

    # Agent
    AGENT_INTERVENTION_REQUESTED = "agent_intervention_requested"
    SCHEDULED_CHECKIN = "scheduled_checkin"

    # User
    USER_MESSAGE = "user_message"
    USER_DIRECT_MESSAGE = "user_direct_message"
    USER_EMOTIONAL_STATE = "user_emotional_state"


class AgentId(str, Enum):
    """The five council members."""

    FREYA = "freya"
    ALBEDO = "albedo"
    ANYA = "anya"
    ZEROTWO = "zerotwo"
    MOHINI = "mohini"


class CallPriority(str, Enum):
    """LLM call priority — maps to model routing."""

    HIGH = "high"        # Pro model
    STANDARD = "standard"  # Flash
    LOW = "low"          # Flash Lite


# =============================================================================
# TASK MODELS
# =============================================================================


class Subtask(BaseModel):
    """Represents one of three standard subtasks within a task."""

    name: str
    completed: bool = False
    points: int = 0
    slider_val: int = 0  # 0 to task.points*0.2, for Be_attentive

    @property
    def is_be_attentive(self) -> bool:
        return self.name == "Be_attentive"


class Task(BaseModel):
    """
    Core task model. Represents a single time-blocked task in the user's day.

    Points breakdown:
      Start_and_Sit_for_5_mins → 50% of total points
      Complete_the_task        → 30% of total points
      Be_attentive             → 20% of total points (scored via slider_val)
    """

    id: str = ""  # sha256 hash, auto-generated
    date: date
    task: str
    start_time: str  # "HH:MM" 24-hour format
    end_time: str    # "HH:MM" 24-hour format
    points: int = 0
    completed: bool = False
    task_class: TaskClass = TaskClass.UNSPECIFIED
    sub_class: Optional[str] = None
    sub_class2: Optional[str] = None
    slider_val: int = 100
    ps_var: float = 0.0  # Problem-solving hours (for Academics_Selfstudy)

    # The three subtask booleans (flattened from old structure)
    start_and_sit: bool = False
    complete_task: bool = False
    be_attentive: bool = False

    @model_validator(mode="after")
    def generate_id(self) -> "Task":
        if not self.id:
            raw = f"{self.date}|{self.task}|{self.start_time}"
            self.id = hashlib.sha256(raw.encode()).hexdigest()[:16]
        
        # Calculate ps_var for Academics_Selfstudy tasks
        if self.task_class == TaskClass.ACADEMICS_SELFSTUDY and self.ps_var == 0.0:
            try:
                h1, m1 = map(int, self.start_time.split(":"))
                h2, m2 = map(int, self.end_time.split(":"))
                diff_mins = (h2 * 60 + m2) - (h1 * 60 + m1)
                if diff_mins < 0:
                    diff_mins += 1440
                self.ps_var = round(diff_mins / 60.0, 2)
            except Exception:
                self.ps_var = 0.0
                
        return self

    @computed_field
    @property
    def start_time_obj(self) -> time:
        h, m = self.start_time.split(":")
        return time(int(h), int(m))

    @computed_field
    @property
    def end_time_obj(self) -> time:
        h, m = self.end_time.split(":")
        return time(int(h), int(m))

    @property
    def subtask_points(self) -> dict[str, int]:
        """Points allocated to each subtask."""
        sit_pts = int(self.points * 0.5)
        complete_pts = int(self.points * 0.3)
        attentive_pts = self.points - sit_pts - complete_pts
        return {
            "Start_and_Sit_for_5_mins": sit_pts,
            "Complete_the_task": complete_pts,
            "Be_attentive": attentive_pts,
        }

    @property
    def is_deviated(self) -> bool:
        return self.task_class == TaskClass.DEVIATED

    @property
    def is_revived(self) -> bool:
        return self.task_class == TaskClass.REVIVED

    @property
    def ends_next_day(self) -> bool:
        """True for blocks that cross midnight, e.g. Sleep 22:00–06:00 (ends the next day)."""
        return self.end_time_obj < self.start_time_obj

    def is_active_at(self, t: time) -> bool:
        """True if time t (on this task's own date) falls inside the block."""
        if self.ends_next_day:
            return t >= self.start_time_obj
        return self.start_time_obj <= t <= self.end_time_obj

    def is_past_at(self, t: time) -> bool:
        """True if the block ended before time t on its own date.
        A block that crosses midnight never ends on its own date."""
        if self.ends_next_day:
            return False
        return self.end_time_obj < t

    def has_ended_by(self, t: time, day_over: bool = False) -> bool:
        """True if the block has finished by time t (inclusive). If the whole day is
        over (a past date), every block counts as finished."""
        if day_over:
            return True
        if self.ends_next_day:
            return False
        return self.end_time_obj <= t


# =============================================================================
# ANALYTICS MODELS
# =============================================================================


class DailyMetrics(BaseModel):
    """
    Aggregated daily performance metrics for one calendar day.
    Single row per date in the daily_analytics table.
    """

    date: date
    alertness: float = 0.0          # 0–100: weighted avg focus score
    discipline: float = 0.0         # 0–100: % of Start_and_Sit completed
    ps_hrs: float = 0.0             # Problem-solving hours (Academics tasks)
    aura: float = 0.0               # Composite: discipline × ps × streak
    retention_streak: int = 0       # Consistency streak: consecutive days the plan was kept
    happiness: float = 0.0          # User-reported (future feature)
    total_points: int = 0           # Raw points scored
    tasks_completed: int = 0
    tasks_total: int = 0
    # Daily check-in: None = not answered, True = kept commitment, False = "not today"
    commitment_kept: Optional[bool] = None
    computed_at: datetime = Field(default_factory=datetime.now)

    @property
    def completion_rate(self) -> float:
        if self.tasks_total == 0:
            return 0.0
        return self.tasks_completed / self.tasks_total * 100


class HourlyPoint(BaseModel):
    """Points logged in a specific hour on a specific day."""

    date: date
    hour: int  # 0–23
    points: int = 0


# =============================================================================
# MEMORY MODELS
# =============================================================================


class MemoryType(str, Enum):
    """Classification of memory entries."""

    BEHAVIORAL = "behavioral"    # Recurring pattern observed
    EMOTIONAL = "emotional"      # Emotional state / event
    FACTUAL = "factual"          # Hard facts about user
    CONVERSATIONAL = "conversational"  # Exchange with an agent
    PRODUCTIVITY = "productivity"  # Performance milestone / trend
    PREFERENCE = "preference"    # User preferences discovered


class MemoryEntry(BaseModel):
    """
    A single memory entry stored in the long-term memory system.

    Shared memory (agent_id=None) is accessible by all agents.
    Agent-specific memory (agent_id set) is private to that agent.
    """

    id: str = ""
    agent_id: Optional[str] = None   # None = shared across all agents
    memory_type: MemoryType = MemoryType.FACTUAL
    content: str
    tags: list[str] = []
    importance: float = 0.5          # 0.0–1.0, affects retrieval ranking
    created_at: datetime = Field(default_factory=datetime.now)
    last_accessed: datetime = Field(default_factory=datetime.now)
    access_count: int = 0

    @model_validator(mode="after")
    def generate_id(self) -> "MemoryEntry":
        if not self.id:
            raw = f"{self.content[:50]}{self.created_at.isoformat()}"
            self.id = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return self


# =============================================================================
# EVENT MODELS
# =============================================================================


class AppEvent(BaseModel):
    """
    An event that flows through the EventBus.
    Can trigger agent responses, rule evaluations, or analytics updates.
    """

    id: str = ""
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.now)
    payload: dict[str, Any] = {}
    source: str = "system"  # "system", "user", agent_id

    @model_validator(mode="after")
    def generate_id(self) -> "AppEvent":
        if not self.id:
            raw = f"{self.event_type}{self.timestamp.isoformat()}"
            self.id = hashlib.sha256(raw.encode()).hexdigest()[:12]
        return self


# =============================================================================
# AGENT MODELS
# =============================================================================


class AgentMessage(BaseModel):
    """
    A response produced by one AI agent.
    Stored in agent_messages table and displayed to the user.
    """

    id: str = ""
    agent_id: AgentId
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    triggered_by: Optional[EventType] = None
    call_priority: CallPriority = CallPriority.STANDARD
    tokens_used: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    model_used: str = ""
    latency_ms: int = 0
    tool_used: Optional[str] = None   # Tool name if agent used a tool
    debug: Optional[dict] = None

    @model_validator(mode="after")
    def generate_id(self) -> "AgentMessage":
        if not self.id:
            raw = f"{self.agent_id}{self.timestamp.isoformat()}"
            self.id = hashlib.sha256(raw.encode()).hexdigest()[:12]
        return self


class ContextPacket(BaseModel):
    """
    The full context assembled for one agent LLM call.
    Tracks token usage for cost monitoring.
    """

    agent_id: AgentId
    event: AppEvent
    current_tasks: list[Task] = []
    current_task: Optional[Task] = None
    memories: list[MemoryEntry] = []
    recent_messages: list[AgentMessage] = []
    metrics: Optional[DailyMetrics] = None
    estimated_tokens: int = 0


# =============================================================================
# USER MODEL (future multi-user support)
# =============================================================================


class User(BaseModel):
    """Represents one user of the system."""

    id: str
    display_name: str
    tier: UserTier = UserTier.FREE
    created_at: datetime = Field(default_factory=datetime.now)
    timezone: str = "Asia/Kolkata"
    daily_interactions_used: int = 0
    last_active: Optional[datetime] = None


# =============================================================================
# TOOL MODELS
# =============================================================================


class ToolResult(BaseModel):
    """Standardized output from any tool execution."""

    tool_name: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_ms: int = 0
    trace_id: str = ""
