"""
Memory Tools
============
Tools for agents to read from and write to the memory system.

Available tools:
  - store_memory     : Save an observation or fact to long-term memory
  - retrieve_memory  : Search for relevant memories by query or tags
  - get_top_memories : Get most important memories for context building
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from core.models import MemoryEntry, MemoryType
from core.exceptions import ToolExecutionError
from data.repositories.memory_repo import memory_repo
from tools.base_tool import BaseTool, ToolContext


# =============================================================================
# STORE MEMORY
# =============================================================================

class StoreMemoryInput(BaseModel):
    content: str = Field(description="The memory content to store.")
    memory_type: str = Field(
        default="factual",
        description=(
            "Type of memory: 'behavioral' (pattern observed), "
            "'emotional' (emotional state/event), 'factual' (hard fact), "
            "'conversational' (exchange), 'productivity' (milestone), "
            "'preference' (user preference)."
        )
    )
    tags: list[str] = Field(
        default=[],
        description="Tags for retrieval (e.g., ['distraction', 'phone', 'afternoon'])."
    )
    importance: float = Field(
        default=0.5,
        ge=0.0, le=1.0,
        description="Importance 0–1. Higher = retrieved more often."
    )
    shared: bool = Field(
        default=True,
        description="If True, all agents can read this. If False, only the calling agent."
    )


class StoreMemoryOutput(BaseModel):
    memory_id: str
    stored: bool


class StoreMemoryTool(BaseTool):
    name = "store_memory"
    description = (
        "Store an observation, pattern, or fact about the user in long-term memory. "
        "Use this when you notice something important about the user's behavior, "
        "preferences, or patterns that should influence future interactions. "
        "Example: store a behavioral memory when you detect a recurring distraction pattern."
    )
    input_schema = StoreMemoryInput
    output_schema = StoreMemoryOutput

    async def execute(
        self, input: StoreMemoryInput, context: ToolContext
    ) -> StoreMemoryOutput:
        try:
            mem_type = MemoryType(input.memory_type)
        except ValueError:
            mem_type = MemoryType.FACTUAL

        entry = MemoryEntry(
            agent_id=None if input.shared else context.agent_id,
            memory_type=mem_type,
            content=input.content,
            tags=input.tags,
            importance=input.importance,
        )

        try:
            await memory_repo.save(entry)
        except Exception as e:
            raise ToolExecutionError(f"Failed to store memory: {e}") from e

        return StoreMemoryOutput(memory_id=entry.id, stored=True)


# =============================================================================
# RETRIEVE MEMORY
# =============================================================================

class RetrieveMemoryInput(BaseModel):
    query: str = Field(
        description="Natural language query or keyword to search memories."
    )
    tags: list[str] = Field(
        default=[],
        description="Optional tags to filter by."
    )
    limit: int = Field(
        default=6,
        ge=1, le=20,
        description="Maximum number of memories to return."
    )


class RetrieveMemoryOutput(BaseModel):
    memories: list[dict]
    total_found: int


class RetrieveMemoryTool(BaseTool):
    name = "retrieve_memory"
    description = (
        "Search long-term memory for relevant observations about the user. "
        "Use this when you need context about the user's past behavior, "
        "preferences, or patterns before responding."
    )
    input_schema = RetrieveMemoryInput
    output_schema = RetrieveMemoryOutput

    async def execute(
        self, input: RetrieveMemoryInput, context: ToolContext
    ) -> RetrieveMemoryOutput:
        try:
            # Tag-based search first (more precise)
            if input.tags:
                results = await memory_repo.search_by_tags(
                    input.tags, agent_id=context.agent_id, limit=input.limit
                )
            else:
                results = await memory_repo.search_by_content(
                    input.query, agent_id=context.agent_id, limit=input.limit
                )

            # Mark all retrieved memories as accessed
            for mem in results:
                await memory_repo.mark_accessed(mem.id)

        except Exception as e:
            raise ToolExecutionError(f"Failed to retrieve memories: {e}") from e

        return RetrieveMemoryOutput(
            memories=[
                {
                    "id": m.id,
                    "type": m.memory_type.value,
                    "content": m.content,
                    "tags": m.tags,
                    "importance": m.importance,
                    "created_at": m.created_at.isoformat(),
                }
                for m in results
            ],
            total_found=len(results),
        )


# =============================================================================
# GET TOP MEMORIES (for context building — pre-filtered by importance)
# =============================================================================

class GetTopMemoriesInput(BaseModel):
    limit: int = Field(
        default=8,
        ge=1, le=20,
        description="Number of top memories to retrieve."
    )
    memory_type: Optional[str] = Field(
        default=None,
        description="Filter by type: 'behavioral', 'emotional', 'factual', etc."
    )


class GetTopMemoriesOutput(BaseModel):
    memories: list[dict]


class GetTopMemoriesTool(BaseTool):
    name = "get_top_memories"
    description = (
        "Retrieve the most important long-term memories for the current agent. "
        "Returns a ranked list by importance score. Used during context assembly "
        "to ensure the most relevant facts are always in view."
    )
    input_schema = GetTopMemoriesInput
    output_schema = GetTopMemoriesOutput

    async def execute(
        self, input: GetTopMemoriesInput, context: ToolContext
    ) -> GetTopMemoriesOutput:
        try:
            memories = await memory_repo.get_most_important(
                agent_id=context.agent_id, limit=input.limit
            )
            if input.memory_type:
                memories = [m for m in memories if m.memory_type.value == input.memory_type]
        except Exception as e:
            raise ToolExecutionError(f"Failed to retrieve top memories: {e}") from e

        return GetTopMemoriesOutput(
            memories=[
                {
                    "id": m.id,
                    "type": m.memory_type.value,
                    "content": m.content,
                    "importance": m.importance,
                    "tags": m.tags,
                }
                for m in memories
            ]
        )
