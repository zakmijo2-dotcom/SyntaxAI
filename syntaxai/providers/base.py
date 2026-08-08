"""Base interface for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[dict]
    usage: dict
    model: str
    finish_reason: str


class LLMProvider(ABC):
    def __init__(self, api_key: str, model: str, base_url: str = ""):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self._max_tokens = 4000

    @abstractmethod
    def generate(self, prompt: str, context: str = "", 
                 tools: list[str] = None, 
                 tool_descriptions: dict = None) -> LLMResponse:
        pass

    def _build_messages(self, prompt: str, context: str, 
                        tools: list[str] = None,
                        tool_descriptions: dict = None) -> list[dict]:
        messages = [
            {
                "role": "system",
                "content": "You are SyntaxAI, a terminal programming assistant. "
                          "Use tools when needed to interact with files, shell, or git."
            },
            {
                "role": "user",
                "content": f"{context}\n\n{prompt}" if context else prompt
            }
        ]
        
        if tools:
            tool_str = "\n".join(
                f"{t}: {desc}" for t, desc in tool_descriptions.items()
            ) if tool_descriptions else ", ".join(tools)
            messages[1]["content"] += f"\n\nAvailable tools:\n{tool_str}"
        
        return messages


def get_provider_class(provider_name: str):
    providers = {
        "gemini": "syntaxai.providers.gemini.GeminiProvider",
        "deepseek": "syntaxai.providers.deepseek.DeepSeekProvider",
        "nemotron": "syntaxai.providers.nemotron.NemotronProvider",
    }
    
    if provider_name.lower() in providers:
        parts = providers[provider_name.lower()].split(".")
        module_path = ".".join(parts[:-1])
        class_name = parts[-1]
        
        import importlib
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    
    return None