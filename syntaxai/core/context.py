"""Conversation and memory management for SyntaxAI.

Mobile / Termux optimisations
-----------------------------
* **Token-aware trimming** — messages are dropped based on an estimated token
  budget (``max_context_tokens``) rather than a fixed message count, so a
  single huge file read cannot blow the whole context.
* **Priority retention** — the system message and the most recent user request
  are always kept; only older assistant/tool messages are evicted first.
* **Output truncation** — tool/file/shell/git outputs are truncated *before*
  they ever reach the LLM, preventing multi-MB payloads from consuming RAM and
  tokens on small devices.
* **Environment awareness** — the detected environment (Termux, WSL, …) is
  stored so the agent can adapt its behaviour.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field
from pathlib import Path

from syntaxai.core.env import detect_environment, EnvironmentInfo


@dataclass
class Message:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "tool_calls": self.tool_calls,
            "tool_results": self.tool_results,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            tool_calls=data.get("tool_calls", []),
            tool_results=data.get("tool_results", []),
        )


@dataclass
class SkillContext:
    name: str
    description: str
    content: str
    triggers: list[str] = field(default_factory=list)


def truncate_for_context(text: str, limit: int) -> str:
    """Truncate *text* to *limit* chars, keeping head + tail when too long.

    Returns the original string if it fits; otherwise a compacted version with
    an explicit marker so the model knows content was omitted.
    """
    if limit <= 0 or len(text) <= limit:
        return text
    keep_head = max(limit // 2, 200)
    keep_tail = max(limit - keep_head, 200)
    head = text[:keep_head]
    tail = text[-keep_tail:]
    omitted = len(text) - keep_head - keep_tail
    return (
        f"{head}\n\n"
        f"... [output truncated: {omitted} chars omitted of {len(text)} total] ...\n\n"
        f"{tail}"
    )


class ContextManager:
    MAX_MESSAGES = 100

    def __init__(self, config=None):
        self.messages: list[Message] = []
        self.skills: list[SkillContext] = []
        self.current_project_path: Optional[Path] = None
        self.config = config
        self.env: EnvironmentInfo = detect_environment()

        # Token / size budget (from config, mobile-aware).
        self.token_estimate_chars: int = getattr(config, "token_estimate_chars", 4)
        self.max_context_tokens: int = getattr(config, "max_context_tokens", 32000)
        self.max_tool_output_chars: int = getattr(config, "max_tool_output_chars", 8000)

    # ── token accounting ──────────────────────────────────────────────────────
    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // self.token_estimate_chars)

    def estimate_message_tokens(self, msg: Message) -> int:
        total = self.estimate_tokens(msg.content)
        for tr in msg.tool_results:
            total += self.estimate_tokens(str(tr.get("result", "")))
            total += self.estimate_tokens(str(tr.get("error", "")))
        return total

    def total_tokens(self) -> int:
        return sum(self.estimate_message_tokens(m) for m in self.messages)

    # ── mutation ───────────────────────────────────────────────────────────────
    def add_message(
        self,
        role: str,
        content: str,
        tool_calls: list[dict] = None,
        tool_results: list[dict] = None,
    ) -> None:
        # Tool results are pre-truncated so they never enter the store untrimmed.
        if tool_results:
            tool_results = [
                {
                    **tr,
                    "result": truncate_for_context(
                        str(tr.get("result", "")), self.max_tool_output_chars
                    ),
                }
                for tr in tool_results
            ]
        msg = Message(
            role=role,
            content=content,
            tool_calls=tool_calls or [],
            tool_results=tool_results or [],
        )
        self.messages.append(msg)
        self._trim_messages()

    def _trim_messages(self) -> None:
        # 1. Hard cap by message count (keep system messages).
        if len(self.messages) > self.MAX_MESSAGES:
            system_msgs = [m for m in self.messages if m.role == "system"]
            rest = [m for m in self.messages if m.role != "system"]
            rest = rest[-self.MAX_MESSAGES:]
            self.messages = system_msgs + rest

        # 2. Token budget: evict oldest *non-system*, *non-latest-user* messages.
        while self.total_tokens() > self.max_context_tokens and len(self.messages) > 1:
            removed = False
            for i, m in enumerate(self.messages):
                if m.role == "system":
                    continue
                # Keep the most recent user turn (priority retention).
                if i == len(self.messages) - 1 and m.role == "user":
                    continue
                del self.messages[i]
                removed = True
                break
            if not removed:
                break

    # ── serialisation ──────────────────────────────────────────────────────────
    def get_context_string(self) -> str:
        lines = []
        for msg in self.messages[-self.MAX_MESSAGES:]:
            lines.append(f"<{msg.role}>")
            lines.append(msg.content)
            if msg.tool_calls:
                lines.append(f"Tool calls: {msg.tool_calls}")
            if msg.tool_results:
                lines.append(f"Tool results: {msg.tool_results}")
        return "\n".join(lines)

    def get_messages_for_provider(self) -> list[dict]:
        result = []
        skill_intro = self._get_skills_context()
        if skill_intro:
            result.append({"role": "system", "content": skill_intro})

        for msg in self.messages[-self.MAX_MESSAGES:]:
            content = truncate_for_context(msg.content, self.max_tool_output_chars)
            tool_results = [
                {
                    **tr,
                    "result": truncate_for_context(
                        str(tr.get("result", "")), self.max_tool_output_chars
                    ),
                }
                for tr in msg.tool_results
            ]
            result.append({
                "role": msg.role,
                "content": content,
                "tool_calls": msg.tool_calls,
                "tool_results": tool_results,
            })
        return result

    def _get_skills_context(self) -> str:
        if not self.skills:
            return ""
        index_lines = [f"- {s.name}: {s.description}" for s in self.skills]
        header = "Available skills:\n" + "\n".join(index_lines)
        # Full body is only included for skills whose content was lazily loaded.
        loaded = [s for s in self.skills if s.content]
        if not loaded:
            return header
        full_parts = [f"Skill: {s.name}\n{s.content}" for s in loaded]
        return header + "\n\n" + "\n\n".join(full_parts)

    # ── environment helpers ─────────────────────────────────────────────────────
    def env_note(self) -> str:
        """Capability note for the system prompt (empty on desktop OSes)."""
        if self.env.is_termux or self.env.is_mobile:
            return self.env.capability_note()
        return ""

    def set_environment(self, env: EnvironmentInfo) -> None:
        self.env = env

    def clear(self) -> None:
        self.messages = []
        self.skills = []

    def set_project_path(self, path: str) -> None:
        self.current_project_path = Path(path).resolve()

    def needs_heavy_model(self, task_description: str) -> bool:
        heavy_keywords = [
            "refactor", "rewrite", "architect", "design", "complex",
            "integrate", "analyze", "deep", "extensive",
        ]
        desc_lower = task_description.lower()
        return any(keyword in desc_lower for keyword in heavy_keywords)
