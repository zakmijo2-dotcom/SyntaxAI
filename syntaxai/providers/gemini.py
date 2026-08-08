"""Google Gemini provider for SyntaxAI."""

from __future__ import annotations

import json
import logging
from typing import Iterator

from syntaxai.providers.base import LLMProvider, LLMResponse, ToolSchema

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    from google.generativeai.types import FunctionDeclaration, Tool as GeminiTool
    _GEMINI_AVAILABLE = True
except ImportError:
    _GEMINI_AVAILABLE = False


class GeminiProvider(LLMProvider):
    """Google Gemini LLM provider with native function-calling support."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash",
                 base_url: str = "") -> None:
        super().__init__(api_key, model, base_url)
        if _GEMINI_AVAILABLE:
            genai.configure(api_key=api_key)

    # ── public ─────────────────────────────────────────────────────────────────
    def generate(
        self,
        messages: list[dict],
        tool_schemas: list[ToolSchema] | None = None,
    ) -> LLMResponse:
        if not _GEMINI_AVAILABLE:
            return self._unavailable_response()

        try:
            gemini_tools = self._build_tools(tool_schemas) if tool_schemas else None
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=self._max_tokens,
                temperature=0.7,
            )
            model = genai.GenerativeModel(
                model_name=self.model,
                generation_config=generation_config,
                tools=gemini_tools,
            )
            gemini_history, last_user_msg = self._convert_messages(messages)
            chat = model.start_chat(history=gemini_history)
            response = chat.send_message(last_user_msg)
            return self._parse_response(response)
        except Exception as exc:
            logger.error("Gemini generate error: %s", exc)
            return LLMResponse(
                content=f"Gemini error: {exc}",
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
        if not _GEMINI_AVAILABLE:
            yield "Gemini SDK not installed."
            return

        try:
            model = genai.GenerativeModel(model_name=self.model)
            gemini_history, last_user_msg = self._convert_messages(messages)
            chat = model.start_chat(history=gemini_history)
            for chunk in chat.send_message(last_user_msg, stream=True):
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
            logger.error("Gemini stream error: %s", exc)
            yield f"[stream error: {exc}]"

    # ── private ────────────────────────────────────────────────────────────────
    @staticmethod
    def _build_tools(schemas: list[ToolSchema]) -> list:
        declarations = []
        for s in schemas:
            props = {}
            required = s.parameters.get("required", [])
            for name, info in s.parameters.get("properties", {}).items():
                gtype = {"string": "STRING", "integer": "INTEGER",
                         "number": "NUMBER", "boolean": "BOOLEAN"}.get(
                    info.get("type", "string"), "STRING"
                )
                props[name] = genai.protos.Schema(
                    type=getattr(genai.protos.Type, gtype),
                    description=info.get("description", ""),
                )
            declarations.append(
                FunctionDeclaration(
                    name=s.name,
                    description=s.description,
                    parameters=genai.protos.Schema(
                        type=genai.protos.Type.OBJECT,
                        properties=props,
                        required=required,
                    ),
                )
            )
        return [GeminiTool(function_declarations=declarations)]

    @staticmethod
    def _convert_messages(messages: list[dict]) -> tuple[list, str]:
        """Convert OpenAI-style messages to Gemini chat history + last user turn."""
        history = []
        for msg in messages[:-1]:
            role = msg["role"]
            content = msg.get("content", "")
            if role == "system":
                continue
            gemini_role = "model" if role in ("assistant", "tool") else "user"
            history.append({"role": gemini_role, "parts": [content]})

        last = messages[-1] if messages else {}
        return history, last.get("content", "")

    @staticmethod
    def _parse_response(response) -> LLMResponse:
        tool_calls: list[dict] = []
        content = ""

        try:
            candidate = response.candidates[0]
            for part in candidate.content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    tool_calls.append({
                        "name": fc.name,
                        "arguments": dict(fc.args) if fc.args else {},
                    })
                elif hasattr(part, "text") and part.text:
                    content += part.text
        except (IndexError, AttributeError):
            try:
                content = response.text or ""
            except Exception:
                pass

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage={},
            model="gemini",
            finish_reason="stop" if not tool_calls else "tool_calls",
        )

    @staticmethod
    def _unavailable_response() -> LLMResponse:
        return LLMResponse(
            content="google-generativeai SDK not installed. Run: pip install google-generativeai",
            tool_calls=[],
            usage={},
            model="gemini",
            finish_reason="error",
        )
