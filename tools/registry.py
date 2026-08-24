"""
Tool Registry
=============
Central registry for all tools in the Feynlist system.

Responsibilities:
  - Register tools at startup
  - Resolve tools by name
  - Enforce per-agent permission lists (from persona YAML configs)
  - Execute tools with agent context
  - List available tools for a given agent (used in prompt building)
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

from core.models import ToolResult
from core.exceptions import ToolNotFoundError, ToolPermissionError
from tools.base_tool import BaseTool, ToolContext


class ToolRegistry:
    """
    Singleton registry for all tools.
    Register tools at startup via register().
    Execute tools via execute().
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        # Maps agent_id → set of allowed tool names
        # None entry means "all tools" (no restriction)
        self._agent_permissions: dict[str, Optional[set[str]]] = {}

    # ------------------------------------------------------------------
    # REGISTRATION
    # ------------------------------------------------------------------

    def register(
        self,
        tool: BaseTool,
        allowed_agents: Optional[list[str]] = None,
    ) -> None:
        """
        Register a tool in the registry.

        Args:
            tool: The tool instance to register.
            allowed_agents: If None, all agents can use this tool.
                            If a list, only those agents can call it.
        """
        if not tool.name:
            raise ValueError(f"Tool {type(tool).__name__} has no name defined.")

        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' is already registered — overwriting.")

        self._tools[tool.name] = tool

        # Store permissions on the tool itself (used in safe_execute)
        if allowed_agents is not None:
            tool.allowed_agents = allowed_agents

        logger.debug(
            f"Registered tool: '{tool.name}' "
            f"(agents: {allowed_agents or 'all'})"
        )

    def register_many(
        self,
        tools: list[BaseTool],
        allowed_agents: Optional[list[str]] = None,
    ) -> None:
        """Register multiple tools at once with the same permission set."""
        for tool in tools:
            self.register(tool, allowed_agents=allowed_agents)

    # ------------------------------------------------------------------
    # ACCESS
    # ------------------------------------------------------------------

    def get(self, tool_name: str) -> BaseTool:
        """Get a tool by name. Raises ToolNotFoundError if not registered."""
        if tool_name not in self._tools:
            raise ToolNotFoundError(tool_name)
        return self._tools[tool_name]

    def get_for_agent(self, agent_id: str) -> list[BaseTool]:
        """
        Returns all tools available to a specific agent.
        Filters by allowed_agents list on each tool.
        """
        result = []
        for tool in self._tools.values():
            if tool.allowed_agents is None:
                result.append(tool)
            elif agent_id in tool.allowed_agents:
                result.append(tool)
        return result

    def list_all(self) -> list[str]:
        """Returns names of all registered tools."""
        return list(self._tools.keys())

    def get_tool_descriptions_for_agent(self, agent_id: str) -> list[dict]:
        """
        Returns schema dicts for all tools available to an agent.
        Used to build the agent's system prompt tool section.
        """
        return [t.to_schema_dict() for t in self.get_for_agent(agent_id)]

    # ------------------------------------------------------------------
    # EXECUTION
    # ------------------------------------------------------------------

    async def execute(
        self,
        tool_name: str,
        raw_input: dict,
        context: ToolContext,
    ) -> ToolResult:
        """
        Execute a registered tool by name.
        Always returns a ToolResult — never raises.
        """
        try:
            tool = self.get(tool_name)
        except ToolNotFoundError as e:
            logger.error(f"TOOL_NOT_FOUND tool={tool_name} agent={context.agent_id}")
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
                trace_id=context.trace_id,
            )

        return await tool.safe_execute(raw_input, context)

    # ------------------------------------------------------------------
    # DIAGNOSTICS
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"ToolRegistry({len(self._tools)} tools: "
            f"{', '.join(self._tools.keys())})"
        )


# Singleton — import and use this everywhere
tool_registry = ToolRegistry()
