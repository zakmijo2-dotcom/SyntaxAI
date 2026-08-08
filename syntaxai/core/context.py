"""Conversation and memory management for SyntaxAI."""

import os
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field
from pathlib import Path


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
            "tool_results": self.tool_results
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            tool_calls=data.get("tool_calls", []),
            tool_results=data.get("tool_results", [])
        )


@dataclass
class SkillContext:
    name: str
    description: str
    content: str
    triggers: list[str] = field(default_factory=list)


class ContextManager:
    MAX_MESSAGES = 100
    MAX_TOKENS = 16000

    def __init__(self, config=None):
        self.messages: list[Message] = []
        self.skills: list[SkillContext] = []
        self.current_project_path: Optional[Path] = None
        self.config = config

    def add_message(self, role: str, content: str, 
                    tool_calls: list[dict] = None,
                    tool_results: list[dict] = None) -> None:
        msg = Message(
            role=role,
            content=content,
            tool_calls=tool_calls or [],
            tool_results=tool_results or []
        )
        self.messages.append(msg)
        self._trim_messages()

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
            result.append({
                "role": "system",
                "content": skill_intro
            })
        
        for msg in self.messages[-self.MAX_MESSAGES:]:
            result.append(msg.to_dict())
        return result

    def _get_skills_context(self) -> str:
        if not self.skills:
            return ""
        skill_texts = []
        for skill in self.skills:
            skill_texts.append(f"Skill: {skill.name}\n{skill.description}\n{skill.content}")
        return "\n".join(skill_texts)

    def _trim_messages(self) -> None:
        if len(self.messages) > self.MAX_MESSAGES:
            self.messages = self.messages[-self.MAX_MESSAGES:]

    def clear(self) -> None:
        self.messages = []
        self.skills = []

    def set_project_path(self, path: str) -> None:
        self.current_project_path = Path(path).resolve()

    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    def needs_heavy_model(self, task_description: str) -> bool:
        heavy_keywords = ["refactor", "rewrite", "architect", "design", "complex", 
                          "integrate", "analyze", "deep", "extensive"]
        desc_lower = task_description.lower()
        return any(keyword in desc_lower for keyword in heavy_keywords)