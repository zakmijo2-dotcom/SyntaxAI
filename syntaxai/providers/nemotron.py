"""NVIDIA Nemotron provider for SyntaxAI (OpenAI-compatible NIM API)."""

from __future__ import annotations

import json
import logging
from typing import Iterator

from syntaxai.providers.base import LLMProvider, LLMResponse, ToolSchema

logger = logging.getLogger(__name__)

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

_BASE_URL = "https://integrate.api.nvidia.com"


class NemotronProvider(LLMProvider):
    """NVIDIA Nemotron provider via the NVIDIA NIM OpenAI-compatible API."""

    def __init__(self, api_key: str,
                 model: str = "nvidia/nemotron-mini-4b-instruct",
                 base_url: str = "") -> None:
        super().__init__(api_key, model, base_url or _BASE_URL)

    def generate(
        self,
        messages: list[dict],
        tool_schemas: list[ToolSchema] | None = None,
    ) -> LLMResponse:
        if not _HTTPX_AVAILABLE:
            return self._unavailable_response("httpx")

        body: dict = {
            "model": self.model,
            "messages": self._ensure_system(messages),
            "max_tokens": self._max_tokens,
            "temperature": 0.7,
            "stream": False,
        }

        if tool_schemas:
            body["tools"] = [s.to_openai_format() for s in tool_schemas]
            body["tool_choice"] = "auto"

        try:
            r = httpx.post(
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=60.0,
            )
            r.raise_for_status()
            return self._parse(r.json())
        except Exception as exc:
            logger.error("Nemotron generate error: %s", exc)
            return LLMResponse(
                content=f"Nemotron error: {exc}",
                tool_calls=[],
                usage={},
                model=self.model,
                finish_reason="error",
            )

    def stream(
        self,
        messages: list[dict],
        tool_schemas: list[ToolSchema] | None = None,
    ) -> Iterator[str]:
        if not _HTTPX_AVAILABLE:
            yield "httpx not installed."
            return

        body: dict = {
            "model": self.model,
            "messages": self._ensure_system(messages),
            "max_tokens": self._max_tokens,
            "temperature": 0.7,
            "stream": True,
        }

        try:
            with httpx.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=120.0,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                        delta = chunk["choices"][0].get("delta", {})
                        text = delta.get("content") or ""
                        if text:
                            yield text
                    except (json.JSONDecodeError, KeyError):
                        pass
        except Exception as exc:
            logger.error("Nemotron stream error: %s", exc)
            yield f"[stream error: {exc}]"

    @staticmethod
    def _parse(data: dict) -> LLMResponse:
        tool_calls: list[dict] = []
        content = ""
        finish = "stop"

        try:
            choice = data["choices"][0]
            msg = choice.get("message", {})
            content = msg.get("content") or ""
            finish = choice.get("finish_reason", "stop")

            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function", {})
                raw_args = fn.get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append({
                    "id": tc.get("id", fn.get("name", "")),
                    "name": fn.get("name", ""),
                    "arguments": args,
                })
        except (KeyError, IndexError) as exc:
            logger.warning("Nemotron parse error: %s", exc)

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=data.get("usage", {}),
            model=data.get("model", "nemotron"),
            finish_reason=finish,
        )

    @staticmethod
    def _unavailable_response(dep: str) -> LLMResponse:
        return LLMResponse(
            content=f"{dep} not installed. Run: pip install {dep}",
            tool_calls=[],
            usage={},
            model="nemotron",
            finish_reason="error",
        )
