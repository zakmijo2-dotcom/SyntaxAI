"""DeepSeek V4 Flash provider for SyntaxAI."""

import json
from typing import Optional

from syntaxai.providers.base import LLMProvider, LLMResponse

try:
    import httpx
    DEEPSEEK_AVAILABLE = True
except ImportError:
    DEEPSEEK_AVAILABLE = False


class DeepSeekProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "deepseek-chat", 
                 base_url: str = ""):
        super().__init__(api_key, model, base_url or "https://api.deepseek.com")

    def generate(self, prompt: str, context: str = "", 
                 tools: list[str] = None,
                 tool_descriptions: dict = None) -> LLMResponse:
        if not DEEPSEEK_AVAILABLE:
            return self._fallback_response(prompt, context)
        
        try:
            messages = self._build_messages(prompt, context, tools, tool_descriptions)
            
            payloads = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": self._max_tokens,
                "top_p": 0.95,
                "stream": False
            }
            
            if tool_descriptions:
                tool_schema = [{
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": desc.split(":")[0] if ":" in desc else desc[:200],
                        "parameters": {
                            "type": "object",
                            "properties": {}
                        }
                    }
                } for name, desc in tool_descriptions.items()]
                payloads["tools"] = tool_schema

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            response = httpx.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=payloads,
                timeout=60.0
            )

            if response.status_code != 200:
                return self._fallback_response(prompt, context, f"HTTP {response.status_code}")

            data = response.json()
            
            tool_calls = []
            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                if "message" in choice:
                    message = choice["message"]
                    if "tool_calls" in message and message["tool_calls"]:
                        for tc in message["tool_calls"]:
                            if "function" in tc:
                                tool_calls.append({
                                    "name": tc["function"]["name"],
                                    "arguments": tc["function"].get("arguments", {})
                                })
                    if "content" in message:
                        content = message["content"]
                    else:
                        content = ""
                else:
                    content = ""
            else:
                content = ""

            usage = data.get("usage", {})
            
            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                usage=usage,
                model=self.model,
                finish_reason=data.get("choices", [{}])[0].get("finish_reason", "stop")
            )

        except Exception as e:
            return self._fallback_response(prompt, context, str(e))

    def _fallback_response(self, prompt: str, context: str, error: str = "") -> LLMResponse:
        return LLMResponse(
            content=f"Error connecting to DeepSeek API: {error}\n\nPrompt: {prompt[:100]}",
            tool_calls=[],
            usage={},
            model=self.model,
            finish_reason="error"
        )


class DeepSeekV4FlashProvider(DeepSeekProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key, model="deepseek-v4-flash", backend="https://api.deepseek.com")