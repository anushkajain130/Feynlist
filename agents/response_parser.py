"""
Agent Response Parser
=====================
Cleans and validates the raw LLM response before it's displayed to the user.

Responsibilities:
  - Strip markdown code fences, extra whitespace, and system artifacts
  - Extract tool calls if the agent chose to use a tool (function-calling mode)
  - Enforce response length limits (characters / tokens)
  - Detect if the model returned an error or refusal

Response format from agents:
  - Normal text response → returned as-is after cleaning
  - Tool call JSON → parsed, executed, then the tool result is re-injected (V2)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

from loguru import logger


@dataclass
class ParsedResponse:
    """The clean output of the parser."""
    content: str                           # Display-ready text
    raw: str                               # Original LLM output (for logging)
    has_tool_call: bool = False
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None
    is_refusal: bool = False
    token_estimate: int = 0


# Phrases that indicate a model refusal / safety block
REFUSAL_PATTERNS = [
    "i cannot", "i'm unable to", "i am unable to",
    "i'm not able to", "i cannot comply",
    "as an ai", "as a language model",
]

# Max chars for a single agent response (avoids wall-of-text responses)
MAX_RESPONSE_CHARS = 1200


class ResponseParser:
    """
    Parses and cleans raw LLM responses from agent runtime.
    """

    def parse(self, raw: str, agent_id: str = "", truncated: bool = False) -> ParsedResponse:
        """
        Main entry point. Takes raw LLM output, returns ParsedResponse.
        """
        if not raw or not raw.strip():
            logger.warning(f"ResponseParser[{agent_id}]: Empty response from LLM.")
            return ParsedResponse(
                content="...",
                raw=raw or "",
                token_estimate=0,
            )

        # 1. Check for tool call JSON (agent chose to use a tool)
        tool_call = self._extract_tool_call(raw)
        if tool_call:
            logger.debug(f"ResponseParser[{agent_id}]: Tool call detected: {tool_call['tool']}")
            return ParsedResponse(
                content="",
                raw=raw,
                has_tool_call=True,
                tool_name=tool_call["tool"],
                tool_args=tool_call.get("args", {}),
            )

        # 2. Clean the text
        cleaned = self._clean(raw)

        # 3. Check for refusal
        is_refusal = any(p in cleaned.lower() for p in REFUSAL_PATTERNS)
        if is_refusal:
            logger.warning(f"ResponseParser[{agent_id}]: Possible refusal detected.")

        # 4. If the model hit its token limit, don't show a half sentence
        if truncated:
            cleaned = self._trim_to_sentence(cleaned)
            logger.debug(f"ResponseParser[{agent_id}]: trimmed token-limited reply to last full sentence.")

        # 5. Enforce length limit (cut at a sentence boundary where possible)
        if len(cleaned) > MAX_RESPONSE_CHARS:
            cleaned = self._trim_to_sentence(cleaned[:MAX_RESPONSE_CHARS])
            logger.debug(f"ResponseParser[{agent_id}]: Response truncated to {MAX_RESPONSE_CHARS} chars.")

        return ParsedResponse(
            content=cleaned,
            raw=raw,
            is_refusal=is_refusal,
            token_estimate=len(cleaned) // 4,
        )

    @staticmethod
    def _trim_to_sentence(text: str) -> str:
        """Cut back to the last complete sentence; if there is none, end with an ellipsis."""
        text = text.rstrip()
        if not text or text[-1] in ".!?…":
            return text
        ends = [m.end() for m in re.finditer(r"[.!?…](?=[\s\"')\]]|$)", text)]
        if ends:
            return text[:ends[-1]].rstrip()
        return text.rsplit(" ", 1)[0].rstrip(",;:—- ") + "…"

    def _clean(self, text: str) -> str:
        """Remove markdown artifacts and normalize whitespace."""
        # Strip code fences
        text = re.sub(r"```[\w]*\n?", "", text)
        text = re.sub(r"```", "", text)

        # Strip leading/trailing whitespace
        text = text.strip()

        # Collapse 3+ consecutive newlines → 2
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Remove common LLM prefixes ("Sure!", "Of course!", etc.)
        prefixes = [
            r"^(Sure,? ?!?\s+)", r"^(Of course!?\s+)",
            r"^(Certainly!?\s+)", r"^(Absolutely!?\s+)",
            r"^(Great!?\s+)",
        ]
        for p in prefixes:
            text = re.sub(p, "", text, flags=re.IGNORECASE)

        return text.strip()

    @staticmethod
    def _extract_tool_call(text: str) -> Optional[dict]:
        """
        Detect and parse a tool call JSON block.
        Agents emit tool calls in this format:

            <tool_call>
            {"tool": "get_current_tasks", "args": {"include_completed": true}}
            </tool_call>
        """
        match = re.search(r"<tool_call>(.*?)</tool_call>", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            return None


# Singleton
response_parser = ResponseParser()
