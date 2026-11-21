"""
Context Builder
===============
Assembles the full context packet sent to an agent's LLM call.

Order of assembly (token budget enforced):
  1. System prompt (persona definition)
  2. Relevant memories (retriever)
  3. Current analytics snapshot
  4. Task status summary
  5. Time context
  6. Recent conversation history (short-term memory)
  7. User message

The context builder is called by AgentRuntime before every LLM invocation.
It is stateless — takes data, returns a formatted string.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Optional

from loguru import logger

from core.models import AgentId, DailyMetrics, MemoryEntry
from memory.retriever import memory_retriever
from memory.short_term import SessionMemory
from data.repositories.analytics_repo import analytics_repo
from data.repositories.task_repo import task_repo
from tools.task_tools import GetTaskSummaryTool
from tools.time_tools import GetTimeContextTool
from tools.base_tool import ToolContext
from core import clock


class ContextBuilder:
    """
    Assembles the full context string for an LLM call.

    Example output structure:
        --- MEMORY ---
        [behavioral] User deviates around 14:00...

        --- STATUS ---
        3/8 tasks done. Currently: 'Differential Equations'. 5 remaining.

        --- METRICS ---
        Today: discipline=82% alertness=71% streak=7d aura=2.41

        --- TIME ---
        14:23 | Thursday | 43% through the day

        --- CONVERSATION ---
        [14:10] Freya: You missed your math block again.

        --- USER ---
        I just finished Differential Equations!
    """

    async def build(
        self,
        agent_id: AgentId,
        user_message: str,
        session: SessionMemory,
        memory_query: Optional[str] = None,
        memory_tags: Optional[list[str]] = None,
    ) -> tuple[str, dict]:
        """
        Build the full context string for one LLM call.

        Args:
            agent_id: Which agent is calling (determines memory scope)
            user_message: The raw message from the user
            session: This agent's SessionMemory instance
            memory_query: Optional keyword to focus memory retrieval
            memory_tags: Optional tags to filter memories

        Returns:
            A tuple of (Formatted context string, debug_data dictionary).
        """
        ctx = ToolContext(agent_id=agent_id.value)
        sections = []
        debug_data = {
            "memory_count": 0,
            "retrieved_memories": []
        }

        # 1. Memories
        try:
            memories = await memory_retriever.retrieve(
                agent_id=agent_id.value,
                query=memory_query or user_message,
                tags=memory_tags,
                max_entries=6,
                max_tokens=800,
            )
            if memories:
                debug_data["memory_count"] = len(memories)
                debug_data["retrieved_memories"] = [m.content for m in memories]
                mem_text = memory_retriever.format_for_prompt(memories)
                sections.append(f"--- MEMORY ---\n{mem_text}")
        except Exception as e:
            logger.warning(f"ContextBuilder: memory retrieval failed: {e}")

        # 2. Task status
        try:
            tool = GetTaskSummaryTool()
            result = await tool.safe_execute({}, ctx)
            if result.success and result.data:
                summary = result.data.get("summary", "")
                stats = result.data.get("stats", {})
                sections.append(
                    f"--- TASK STATUS ---\n{summary}\n"
                    f"Completion: {stats.get('completion_pct', 0)}% "
                    f"({stats.get('completed', 0)}/{stats.get('total', 0)} tasks)"
                )
        except Exception as e:
            logger.warning(f"ContextBuilder: task status failed: {e}")

        # 3. Analytics snapshot
        try:
            metrics = await analytics_repo.get_metrics_for_date(clock.today())
            if metrics:
                sections.append(self._format_metrics(metrics))
        except Exception as e:
            logger.warning(f"ContextBuilder: analytics failed: {e}")

        # 4. Time context
        try:
            time_tool = GetTimeContextTool()
            time_result = await time_tool.safe_execute({}, ctx)
            if time_result.success and time_result.data:
                d = time_result.data
                current = d.get("current_task_name", "None")
                next_t = d.get("next_task_name", "None")
                mins = d.get("minutes_until_next_task", "?")
                sections.append(
                    f"--- TIME ---\n"
                    f"{d.get('current_time')} | {d.get('day_of_week')} | "
                    f"{d.get('day_progress_pct')}% through the day\n"
                    f"Active task: {current} | Next: {next_t} (in {mins} min)"
                )
        except Exception as e:
            logger.warning(f"ContextBuilder: time context failed: {e}")

        # 5. Recent conversation history
        try:
            history = session.format_for_prompt(n=6, max_chars_per_msg=250)
            sections.append(f"--- CONVERSATION HISTORY ---\n{history}")
        except Exception as e:
            logger.warning(f"ContextBuilder: session format failed: {e}")

        # 6. User message
        sections.append(f"--- USER MESSAGE ---\n{user_message}")

        return "\n\n".join(sections), debug_data

    @staticmethod
    def _format_metrics(metrics: DailyMetrics) -> str:
        return (
            f"--- PERFORMANCE METRICS ---\n"
            f"Discipline: {metrics.discipline:.1f}% | "
            f"Alertness: {metrics.alertness:.1f}% | "
            f"PS Hours: {metrics.ps_hrs:.1f}h | "
            f"Aura: {metrics.aura:.2f} | "
            f"Consistency streak: {metrics.retention_streak}d\n"
            f"Points: {metrics.total_points} | "
            f"Tasks: {metrics.tasks_completed}/{metrics.tasks_total}"
        )
