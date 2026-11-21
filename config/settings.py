"""
Feynlist Settings
=================
Single source of truth for all configuration.
Loaded from environment variables / .env file.
Never hardcode paths or secrets in source code.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


# Project root is two levels up from this file (config/settings.py)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # AI / LLM
    # -------------------------------------------------------------------------
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")

    @property
    def resolved_api_key(self) -> str:
        """Returns whichever API key is present: GEMINI_API_KEY first, then GOOGLE_API_KEY."""
        return (
            self.gemini_api_key
            or self.google_api_key
            or os.environ.get("GEMINI_API_KEY", "")
            or os.environ.get("GOOGLE_API_KEY", "")
        )

    @property
    def has_api_key(self) -> bool:
        return bool(self.resolved_api_key)

    # Model routing. Free tier only: use Flash or Flash-Lite models (Pro models
    # have no free-tier quota). Personas pick a tier via `model_tier` in their YAML.
    # Set both to whichever model has the higher free daily allowance in AI Studio.
    gemini_model_standard: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL_STANDARD")
    gemini_model_light: str = Field(default="gemini-2.5-flash-lite", alias="GEMINI_MODEL_LIGHT")

    # Thinking budget for 2.5 Flash models (tokens). 0 = off (short replies don't need
    # it and thinking tokens eat into max_output_tokens). -1 = leave the model default.
    gemini_thinking_budget: int = Field(default=0, alias="GEMINI_THINKING_BUDGET")

    def model_for_tier(self, tier: str | None) -> str:
        """'light' -> GEMINI_MODEL_LIGHT, anything else -> GEMINI_MODEL_STANDARD."""
        return self.gemini_model_light if tier == "light" else self.gemini_model_standard

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    database_path: Path = Field(
        default=PROJECT_ROOT / "feynlist.db",
        alias="DATABASE_PATH",
    )

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: Path = Field(
        default=PROJECT_ROOT / "logs" / "feynlist.log",
        alias="LOG_FILE",
    )

    # -------------------------------------------------------------------------
    # Agent Orchestration
    # -------------------------------------------------------------------------
    agent_schedule_interval_seconds: int = Field(
        default=1200, alias="AGENT_SCHEDULE_INTERVAL_SECONDS"
    )
    global_agent_cooldown_seconds: int = Field(
        default=300, alias="GLOBAL_AGENT_COOLDOWN_SECONDS"
    )

    # -------------------------------------------------------------------------
    # Default time zone (IANA name, e.g. "Europe/London") for "today"/"now" and for
    # scheduled jobs. Requests from the browser use the browser's own zone instead.
    # Empty = the server's local time.
    # -------------------------------------------------------------------------
    app_timezone: str = Field(default="", alias="APP_TIMEZONE")

    # -------------------------------------------------------------------------
    # Public demo (evaluator) mode
    # -------------------------------------------------------------------------
    # true = every browser session gets its own throwaway database seeded with
    # sample data (identified by the X-Feynlist-Session header).
    demo_mode: bool = Field(default=False, alias="DEMO_MODE")
    demo_data_dir: Path = Field(default=Path("/tmp/feynlist-demo"), alias="DEMO_DATA_DIR")
    demo_max_sessions: int = Field(default=200, alias="DEMO_MAX_SESSIONS")

    # -------------------------------------------------------------------------
    # Free-tier AI budget (see agents/ai_budget.py)
    # -------------------------------------------------------------------------
    live_replies_per_session: int = Field(default=2, alias="LIVE_REPLIES_PER_SESSION")
    # Live model requests per day across all users (Pacific day). Set it below your
    # AI Studio daily request limit, leaving headroom for your own evals. 0 = no cap.
    live_ai_daily_cap: int = Field(default=20, alias="LIVE_AI_DAILY_CAP")
    live_ai_per_minute: int = Field(default=8, alias="LIVE_AI_PER_MINUTE")
    ai_budget_path: Path = Field(default=Path("/tmp/feynlist-demo/ai_budget.db"), alias="AI_BUDGET_PATH")
    # Scheduled jobs and automatic nudges call the model only when this is true
    # (local/real use). Keep false for the public demo.
    enable_proactive_llm: bool = Field(default=False, alias="ENABLE_PROACTIVE_LLM")

    # Frontend origins allowed to call the API (comma-separated). "*" = any (local dev).
    allowed_origins: str = Field(default="*", alias="ALLOWED_ORIGINS")

    @property
    def allowed_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.allowed_origins.split(",") if o.strip()]

    # (Persona configs live in agents/personas/*.yaml; see agents/runtime.PERSONAS_DIR.)

    # -------------------------------------------------------------------------
    # Analytics thresholds
    # -------------------------------------------------------------------------
    # Alertness EWM weights (today vs yesterday)
    alertness_today_weight: float = 0.85
    alertness_yesterday_weight: float = 0.15

    # Discipline EWM weights
    discipline_today_weight: float = 0.95
    discipline_yesterday_weight: float = 0.05

    # Aura formula: log(1 + streak) to avoid zero-collapse
    # aura = (disc/100)^0.5 * (ps_hrs/ps_target)^0.5 * log(1+streak)
    ps_hrs_target_per_3days: float = 6.0

    # Consistency streak: a day counts if the user checks in "I kept my commitment"
    # or completes at least this share of their planned tasks (0.0–1.0).
    streak_min_completion: float = Field(default=0.5, alias="STREAK_MIN_COMPLETION")


# Singleton — import this everywhere
settings = Settings()
