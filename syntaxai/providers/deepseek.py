"""DeepSeek provider for SyntaxAI (OpenAI-compatible API)."""

from __future__ import annotations

import json
import logging
import time
from typing import Iterator, Optional

from syntaxai.providers.base import LLMProvider, LLMResponse, ToolSchema

logger = logging.getLogger(__name__)

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

_BASE_URL = "https://api.deepseek.com"
_MAX_RETRIES = 3


class DeepSeekProvider(LLMProvider):
    """DeepSeek provider using the OpenAI-compatible REST API.

    Uses a single persistent ``httpx.Client`` for connection reuse and retries
    transient network errors (important on flaky Android/mobile connections).
    """

    def __init__(self, api_key: str, model: str = "deepseek-chat",
                 base_url: str = "", connect_timeout: float = 10.0,
                 read_timeout: float = 60.0) -> None:
        super().__init__(api_key, model, base_url or _BASE_URL,
                         connect_timeout=connect_timeout, read_timeout=read_timeout)
        self._client: Optional["httpx.Client"] = None

    def _get_client(self) -> "httpx.Client":
        if self._client is None:
            timeout = httpx.Timeout(self.connect_timeout, read=self.read_timeout)
            self._client = httpx.Client(timeout=timeout, follow_redirects=True)
        return self._client

    def _post(self, body: dict) -> dict:
        """POST with retry on transient connection/read errors."""
        client = self._get_client()
        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_RETRIES):
            try:
                r = client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                r.raise_for_status()
                return r.json()
            except (httpx.ConnectError, httpx.ReadTimeout,
                    httpx.ConnectTimeout, httpx.RemoteProtocolError) as exc:
                last_exc = exc
                logger.warning("DeepSeek network retry %d/%d: %s",
                               attempt + 1, _MAX_RETRIES, exc)
                time.sleep(0.5 * (2 ** attempt))
            except Exception as exc:
                last_exc = exc
                break
        raise last_exc or RuntimeError("DeepSeek request failed")

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
            return self._parse(self._post(body))
        except Exception as exc:
            logger.error("DeepSeek generate error: %s", exc)
            return LLMResponse(
                content=f"DeepSeek error: {exc}",
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
            timeout = httpx.Timeout(self.connect_timeout, read=self.read_timeout)
            with self._get_client().stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json"},
                json=body,
                timeout=timeout,
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
            logger.error("DeepSeek stream error: %s", exc)
            yield f"[stream error: {exc}]"

    # ── helpers ────────────────────────────────────────────────────────────────
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
            logger.warning("DeepSeek parse error: %s", exc)

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=data.get("usage", {}),
            model=data.get("model", "deepseek"),
            finish_reason=finish,
        )

    @staticmethod
    def _unavailable_response(dep: str) -> LLMResponse:
        return LLMResponse(
            content=f"{dep} not installed. Run: pip install {dep}",
            tool_calls=[],
            usage={},
            model="deepseek",
            finish_reason="error",
        )
