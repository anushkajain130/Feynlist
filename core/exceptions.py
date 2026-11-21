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


# Short, user-safe messages. Raw provider errors are logged server-side only.
AI_UNAVAILABLE_MESSAGES = {
    "no_api_key": (
        "Live AI replies aren't set up on this server, so the Council can't answer "
        "right now. Your plan and stats still work."
    ),
    "quota": (
        "The Council has reached its free AI limit for now. Please try again later. "
        "Your plan and stats still work."
    ),
    "provider_error": (
        "The Council couldn't reply just now. Please try again in a moment. "
        "Your plan and stats still work."
    ),
}


class AgentUnavailableError(AgentRuntimeError):
    """
    The LLM can't be used right now (no key, quota/rate limit, provider error).
    `user_message` is safe to show in the UI; `reason` is a short code.
    """

    def __init__(self, reason: str):
        self.reason = reason if reason in AI_UNAVAILABLE_MESSAGES else "provider_error"
        self.user_message = AI_UNAVAILABLE_MESSAGES[self.reason]
        super().__init__(self.user_message)


def classify_llm_error(exc: BaseException) -> str:
    """Map a provider exception to a reason code without exposing its text."""
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    text = str(exc).lower()
    if code == 429 or "resource_exhausted" in text or "quota" in text or "rate limit" in text:
        return "quota"
    if code in (401, 403) or "api key not valid" in text or "api_key_invalid" in text:
        return "no_api_key"
    return "provider_error"


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



