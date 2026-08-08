"""Gemini LLM provider for SyntaxAI."""

import json
import os
from typing import Optional

from syntaxai.providers.base import LLMProvider, LLMResponse

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash", 
                 base_url: str = ""):
        super().__init__(api_key, model, base_url or "https://generativelanguage.googleapis.com")
        
        if GEMINI_AVAILABLE:
            genai.configure(api_key=api_key)

    def generate(self, prompt: str, context: str = "", 
                 tools: list[str] = None,
                 tool_descriptions: dict = None) -> LLMResponse:
        if not GEMINI_AVAILABLE:
            return self._fallback_response(prompt, context)
        
        try:
            generation_config = {
                "temperature": 0.7,
                "max_output_tokens": self._max_tokens,
                "top_p": 0.95,
                "top_k": 40,
            }

            safety_settings = [
                {"category": "HARM_CATEGORY_ETERNAL_HARM", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUAL_CONTENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]

            model = genai.GenerativeModel(
                model_name=self.model,
                generation_config=generation_config,
                safety_settings=safety_settings
            )

            messages = self._build_messages(prompt, context, tools, tool_descriptions)
            
            response = model.generate_content(
                messages,
                tools=self._build_tool_config(tool_descriptions) if tool_descriptions else None
            )

            tool_calls = []
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            tool_calls.append({
                                "name": part.function_call.name,
                                "arguments": dict(part.function_call.args) if part.function_call.args else {}
                            })

            content = ""
            if hasattr(response, 'text'):
                content = response.text
            elif hasattr(response, 'candidates') and response.candidates:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text'):
                        content += part.text

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                usage={"total_tokens": getattr(response, 'usage', {}).get('total_tokens', 0)},
                model=self.model,
                finish_reason="stop"
            )

        except Exception as e:
            return self._fallback_response(prompt, context, str(e))

    def _build_tool_config(self, tool_descriptions: dict):
        tools_config = []
        for name, desc in tool_descriptions.items():
            tools_config.append({
                "function_declarations": [
                    {
                        "name": name,
                        "description": desc.split(":")[0] if ":" in desc else desc[:100],
                        "parameters": {
                            "type": "object",
                            "properties": {}
                        }
                    }
                ]
            })
        return tools_config

    def _fallback_response(self, prompt: str, context: str, error: str = "") -> LLMResponse:
        return LLMResponse(
            content=f"Error connecting to Gemini API: {error}\n\nPrompt received: {prompt[:100]}",
            tool_calls=[],
            usage={},
            model=self.model,
            finish_reason="error"
        )