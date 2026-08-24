"""
Tool System — Base Tool
=======================
Abstract base class for all tools in the Feynlist tool registry.

Every tool:
  - Has a typed Pydantic input/output schema
  - Validates input before execution
  - Checks agent permissions before execution
  - Traces every call (tool name, agent, duration, success/fail)
  - Returns a structured ToolResult — never raises to the caller
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Optional, Type

from loguru import logger
from pydantic import BaseModel, ValidationError

from core.models import ToolResult
from core.exceptions import ToolPermissionError, ToolValidationError, ToolExecutionError


# =============================================================================
# TOOL CONTEXT
# =============================================================================

class ToolContext(BaseModel):
    """
    Context passed to every tool execution.
    Carries the calling agent's identity and trace information.
    """
    agent_id: Optional[str] = None      # Which agent is calling this tool
    user_id: str = "local"              # User (for future multi-user support)
    trace_id: str = ""                  # Correlates logs across a single agent turn
    session_id: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.trace_id:
            self.trace_id = str(uuid.uuid4())[:8]


# =============================================================================
# BASE TOOL
# =============================================================================

class BaseTool(ABC):
    """
    Abstract base for all Feynlist tools.

    Subclasses must define:
        name: str               — unique identifier (snake_case)
        description: str        — shown to agents in their context prompt
        input_schema: Type[BaseModel]  — Pydantic model for input
        output_schema: Type[BaseModel] — Pydantic model for output

    Subclasses must implement:
        execute(input, context) -> output_schema instance
    """

    name: str = ""
    description: str = ""
    input_schema: Type[BaseModel] = BaseModel
    output_schema: Type[BaseModel] = BaseModel

    # Which agent IDs can use this tool (None = all agents can use it)
    allowed_agents: Optional[list[str]] = None

    @abstractmethod
    async def execute(
        self, input: BaseModel, context: ToolContext
    ) -> BaseModel:
        """
        Core execution logic. Implement in subclasses.
        Should raise ToolExecutionError on failure.
        """
        ...

    async def safe_execute(
        self, raw_input: dict, context: ToolContext
    ) -> ToolResult:
        """
        Public entry point. Wraps execute() with:
          1. Permission check
          2. Input validation (Pydantic)
          3. Execution with timing
          4. Structured error handling
          5. Trace logging
        """
        start_ms = int(time.time() * 1000)

        # 1. Permission check
        if self.allowed_agents is not None and context.agent_id is not None:
            if context.agent_id not in self.allowed_agents:
                err = ToolPermissionError(context.agent_id, self.name)
                logger.warning(
                    f"TOOL_DENIED tool={self.name} agent={context.agent_id} "
                    f"trace={context.trace_id}"
                )
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    error=str(err),
                    trace_id=context.trace_id,
                )

        # 2. Input validation
        try:
            validated_input = self.input_schema.model_validate(raw_input)
        except ValidationError as e:
            logger.warning(
                f"TOOL_VALIDATION_FAILED tool={self.name} "
                f"agent={context.agent_id} errors={e.error_count()}"
            )
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Input validation failed: {e.error_count()} error(s). "
                      f"First: {e.errors()[0]['msg']}",
                trace_id=context.trace_id,
            )

        # 3. Execute
        try:
            result = await self.execute(validated_input, context)
            elapsed = int(time.time() * 1000) - start_ms

            logger.info(
                f"TOOL_OK tool={self.name} agent={context.agent_id} "
                f"duration_ms={elapsed} trace={context.trace_id}"
            )

            return ToolResult(
                tool_name=self.name,
                success=True,
                data=result.model_dump() if isinstance(result, BaseModel) else result,
                execution_ms=elapsed,
                trace_id=context.trace_id,
            )

        except ToolExecutionError as e:
            elapsed = int(time.time() * 1000) - start_ms
            logger.error(
                f"TOOL_FAILED tool={self.name} agent={context.agent_id} "
                f"duration_ms={elapsed} error={e} trace={context.trace_id}"
            )
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(e),
                execution_ms=elapsed,
                trace_id=context.trace_id,
            )

        except Exception as e:
            elapsed = int(time.time() * 1000) - start_ms
            logger.exception(
                f"TOOL_UNEXPECTED_ERROR tool={self.name} agent={context.agent_id} "
                f"duration_ms={elapsed} trace={context.trace_id}"
            )
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Unexpected error: {type(e).__name__}: {e}",
                execution_ms=elapsed,
                trace_id=context.trace_id,
            )

    def to_schema_dict(self) -> dict:
        """
        Returns a dict describing this tool for inclusion in agent prompts.
        Format designed to be readable by the LLM.
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema.model_json_schema(),
        }
