"""Base interface for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator, Optional


@dataclass
class ToolSchema:
    """JSON-Schema-compliant description of a single tool."""
    name: str
    description: str
    parameters: dict = field(default_factory=dict)

    def to_openai_format(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_gemini_format(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[dict]
    usage: dict
    model: str
    finish_reason: str


class LLMProvider(ABC):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "",
        connect_timeout: float = 10.0,
        read_timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self._max_tokens = 4096

    def _timeout(self) -> Optional[object]:
        """Return an ``httpx.Timeout`` for subclasses that use httpx."""
        try:
            import httpx

            return httpx.Timeout(self.connect_timeout, read=self.read_timeout)
        except ImportError:
            return None

    @abstractmethod
    def generate(
        self,
        messages: list[dict],
        tool_schemas: list[ToolSchema] | None = None,
    ) -> LLMResponse:
        """Send *messages* to the model and return a response.

        Args:
            messages: Full conversation history in OpenAI-style format.
            tool_schemas: Optional list of tools the model may call.
        """

    def stream(
        self,
        messages: list[dict],
        tool_schemas: list[ToolSchema] | None = None,
    ) -> Iterator[str]:
        """Stream response tokens. Default implementation yields all at once."""
        response = self.generate(messages, tool_schemas)
        if response.content:
            yield response.content

    def _system_prompt(self) -> str:
        return (
            "You are SyntaxAI, a terminal programming assistant. "
            "Use the provided tools to read/write files, run shell commands, "
            "and interact with git. Be concise, accurate, and safe."
        )

    def _ensure_system(self, messages: list[dict]) -> list[dict]:
        """Prepend a system message if one is not already present."""
        if messages and messages[0].get("role") == "system":
            return messages
        return [{"role": "system", "content": self._system_prompt()}] + messages
