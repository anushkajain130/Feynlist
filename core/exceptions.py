"""
Core Exceptions
===============
All domain-level exceptions for Feynlist.
Catch these at the boundary layers (tools, agents, API).
"""


class FeynlistError(Exception):
    """Base exception for all Feynlist errors."""


# --- Database ---
class DatabaseError(FeynlistError):
    """Raised on SQLite errors."""


class RecordNotFoundError(DatabaseError):
    """Raised when a requested record does not exist."""

    def __init__(self, model: str, id: str):
        super().__init__(f"{model} with id '{id}' not found.")
        self.model = model
        self.id = id


class MigrationError(DatabaseError):
    """Raised when a database migration fails."""


# --- Agent / LLM ---
class AgentError(FeynlistError):
    """Base exception for agent-related errors."""


class LLMCallError(AgentError):
    """Raised when an LLM API call fails after retries."""

    def __init__(self, agent_id: str, reason: str):
        super().__init__(f"LLM call failed for agent '{agent_id}': {reason}")
        self.agent_id = agent_id


class PersonaNotFoundError(AgentError):
    """Raised when a persona config file cannot be loaded."""

    def __init__(self, agent_id: str):
        super().__init__(f"Persona config not found for agent '{agent_id}'.")


class AgentCooldownError(AgentError):
    """Raised when an agent is on cooldown and cannot respond."""

    def __init__(self, agent_id: str, seconds_remaining: int):
        super().__init__(
            f"Agent '{agent_id}' is on cooldown for {seconds_remaining}s."
        )
        self.agent_id = agent_id
        self.seconds_remaining = seconds_remaining


class AgentRuntimeError(AgentError):
    """Raised on unrecoverable agent runtime errors (config missing, LLM failure)."""


# --- Tools ---
class ToolError(FeynlistError):
    """Base exception for tool execution errors."""


class ToolNotFoundError(ToolError):
    """Raised when a tool is not registered in the ToolRegistry."""

    def __init__(self, tool_name: str):
        super().__init__(f"Tool '{tool_name}' is not registered.")


class ToolPermissionError(ToolError):
    """Raised when an agent tries to use a tool it has no access to."""

    def __init__(self, agent_id: str, tool_name: str):
        super().__init__(
            f"Agent '{agent_id}' does not have permission to use tool '{tool_name}'."
        )


class ToolValidationError(ToolError):
    """Raised when tool input fails Pydantic validation."""


class ToolExecutionError(ToolError):
    """Raised when tool execution fails internally."""


# --- Memory ---
class MemoryError(FeynlistError):
    """Base exception for memory system errors."""


class MemoryStoreFull(MemoryError):
    """Raised when short-term memory buffer is at capacity and cannot flush."""


# --- Events ---
class EventBusError(FeynlistError):
    """Raised on event bus publish/subscribe errors."""


# --- Config ---
class ConfigError(FeynlistError):
    """Raised on configuration loading errors."""

    def __init__(self, key: str, reason: str):
        super().__init__(f"Config error for '{key}': {reason}")


# --- Rate Limiting ---
class RateLimitExceeded(FeynlistError):
    """Raised when a user has hit their daily interaction limit."""

    def __init__(self, user_id: str, tier: str, limit: int):
        super().__init__(
            f"User '{user_id}' ({tier} tier) has exceeded daily limit of {limit} interactions."
        )
        self.user_id = user_id
        self.tier = tier
        self.limit = limit
