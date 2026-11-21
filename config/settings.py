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

    # Model routing — stable aliases (no preview suffix, always current)
    model_high_priority: str = "gemini-2.5-pro"
    model_standard: str = "gemini-2.5-flash"
    model_low_priority: str = "gemini-2.5-flash-lite"

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
    # Rate Limiting (interactions per day per tier)
    # -------------------------------------------------------------------------
    free_tier_daily_interactions: int = Field(
        default=8, alias="FREE_TIER_DAILY_INTERACTIONS"
    )
    pro_tier_daily_interactions: int = Field(
        default=40, alias="PRO_TIER_DAILY_INTERACTIONS"
    )
    ultra_tier_daily_interactions: int = Field(
        default=150, alias="ULTRA_TIER_DAILY_INTERACTIONS"
    )

    # -------------------------------------------------------------------------
    # Paths
    # -------------------------------------------------------------------------
    persona_configs_dir: Path = Field(
        default=PROJECT_ROOT / "config" / "persona_configs",
        alias="PERSONA_CONFIGS_DIR",
    )
    assets_dir: Path = Field(
        default=PROJECT_ROOT / "assets",
        alias="ASSETS_DIR",
    )

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
