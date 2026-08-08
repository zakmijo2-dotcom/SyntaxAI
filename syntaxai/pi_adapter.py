"""Pi Agent CLI adapter layer - bridges Pi SDK with SyntaxAI architecture.

This module provides the foundation for SyntaxAI by wrapping pi-py-sdk's agent
capabilities while adding SyntaxAI-specific features like approval workflows,
custom prompts, and coding workflows.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

try:
    from pi_llm import TextContent, UserMessage
    from pi_llm_agent import AgentTool, AgentToolResult
    from pi_py_sdk import MessageUpdateEvent, PiAgent, PiAgentSync
    HAVE_PI_SDK = True
except ImportError:
    HAVE_PI_SDK = False


class ProviderType(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    GOOGLE = "google"
    NVIDIA = "nvidia"


@dataclass
class SyntaxAITool:
    """Tool definition for SyntaxAI - wraps Pi Agent tools with approval."""

    name: str
    description: str
    parameters: dict
    execute: Callable[[dict], Any]
    requires_approval: bool = False
    risk_level: str = "safe"


class PiSyntaxAgent:
    """SyntaxAI's core agent built on Pi Agent CLI.

    This class wraps pi-py-sdk's PiAgent to provide:
    - Multi-provider LLM support
    - Tool execution with approval system
    - Context-aware conversation management
    - Event streaming for real-time updates
    """

    def __init__(
        self,
        model: str = "google/gemini-2.5-flash",
        cwd: str = ".",
        session_id: str | None = None,
        event_sink: Callable[[dict], None] | None = None,
        max_steps: int = 20,
    ) -> None:
        if not HAVE_PI_SDK:
            raise ImportError("pi-py-sdk not installed. Run: pip install pi-py-sdk")

        self.model = model
        self.cwd = Path(cwd).resolve()
        self.session_id = session_id or f"syntaxai-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.event_sink = event_sink
        self.max_steps = max_steps
        self._tools: list[Any] = []
        self._running = False
        self._messages: list[dict] = []

        self._init_system_prompt()

    def _default_api_key(self, provider: str) -> str:
        """Get API key from environment variables."""
        key_var = f"{provider.upper()}_API_KEY"
        return os.environ.get(key_var, "")

    def _init_system_prompt(self) -> None:
        env_info = self._detect_environment()
        env_note = ""
        if env_info.get("is_termux"):
            env_note = "\n\nYou are running in Termux on Android. No sudo, systemd, or Docker available."
        self.system_prompt = f"""You are SyntaxAI, a terminal AI programming assistant.
You have access to tools for reading/writing files, running shell commands, and interacting with git.
Always explain what you are doing and why before calling a tool.
If a tool fails, analyze the error and try a different approach.
Never execute destructive commands without explicit user confirmation.{env_note}"""

    def _detect_environment(self) -> dict:
        """Detect the current environment."""
        return {
            "is_termux": "TERMUX_VERSION" in os.environ,
            "is_codespaces": "CODESPACE_NAME" in os.environ,
            "is_gitpod": "GITPOD_WORKSPACE_URL" in os.environ,
        }

    def _get_approval_handler(self) -> Callable[[str, dict, str], bool]:
        """Return the approval handler for tool execution."""
        from syntaxai.safety.approval import get_approval

        def handler(tool_name: str, args: dict, risk: str = "safe") -> bool:
            if risk == "safe":
                return True
            return get_approval(tool_name, args, risk)

        return handler

    def run(self, query: str) -> str:
        """Run the agent synchronously and return final response."""
        provider = self.model.split("/")[0] if "/" in self.model else self.model
        api_key = self._default_api_key(provider)

        if not api_key:
            return "No API key configured. Set environment variable for your provider."

        try:
            with PiAgentSync(
                model=self.model,
                cwd=str(self.cwd),
            ) as agent:
                agent.set_system_prompt(self.system_prompt)
                result = agent.complete(query)
                if result.content:
                    return result.content[0].text if hasattr(result.content[0], 'text') else str(result.content)
                return str(result)
        except Exception as e:
            return f"Error: {e}"

    def stream(self, query: str) -> None:
        """Run the agent with event streaming. Events are sent via event_sink."""
        provider = self.model.split("/")[0] if "/" in self.model else self.model
        api_key = self._default_api_key(provider)

        if not api_key:
            if self.event_sink:
                self.event_sink({"type": "error", "message": "No API key configured"})
            return

        try:
            with PiAgentSync(
                model=self.model,
                cwd=str(self.cwd),
            ) as agent:
                agent.subscribe(self._event_handler)
                for _ev in agent.prompt_stream(query):
                    pass
        except Exception as e:
            if self.event_sink:
                self.event_sink({"type": "error", "message": str(e)})

    def _event_handler(self, event: Any, cancel: Any) -> None:
        """Handle Pi Agent events and forward to SyntaxAI event sink."""
        if not self.event_sink:
            return

        try:
            if hasattr(event, 'type'):
                etype = event.type

                if etype == "thinking":
                    self.event_sink({"type": "thinking"})
                elif etype == "tool_execution_start":
                    self.event_sink({
                        "type": "tool_start",
                        "tool": getattr(event, 'tool_name', 'unknown'),
                        "args": getattr(event, 'args', {}),
                    })
                elif etype == "tool_execution_end":
                    content = ""
                    if hasattr(event, 'result') and event.result and hasattr(event.result, 'content'):
                        if event.result.content and len(event.result.content) > 0:
                            content = getattr(event.result.content[0], 'text', str(event.result.content[0]))
                    self.event_sink({
                        "type": "tool_end",
                        "tool": getattr(event, 'tool_name', 'unknown'),
                        "success": not getattr(event, 'is_error', False),
                        "result": content,
                    })
                elif etype == "agent_end":
                    final_msg = getattr(event, 'final_message', None)
                    if final_msg and hasattr(final_msg, 'content') and final_msg.content:
                        content = getattr(final_msg.content[0], 'text', '')
                        self.event_sink({"type": "response", "message": content})
                    else:
                        self.event_sink({"type": "response", "message": "Completed"})
                    self.event_sink({"type": "done"})
        except Exception:
            pass

    def prompt(self, user_message: str, system_prompt: str | None = None) -> str:
        """Send a prompt to the agent and get the response."""

        try:
            with PiAgentSync(
                model=self.model,
                cwd=str(self.cwd),
            ) as agent:
                agent.set_system_prompt(system_prompt or self.system_prompt)
                result = agent.complete(user_message)
                if result.content:
                    return result.content[0].text if hasattr(result.content[0], 'text') else str(result.content)
                return ""
        except Exception as e:
            return f"Error: {e}"

    def set_model(self, model: str) -> None:
        """Change the model for subsequent operations."""
        self.model = model

    def add_tool(self, tool: Any) -> None:
        """Add a custom tool to the agent."""
        self._tools.append(tool)

    def run_interactive(self) -> None:
        """Run interactive REPL session."""
        print("\033[1;36m" + "─" * 50 + "\033[0m")
        print("\033[1;36m  SyntaxAI — Terminal AI Programming Assistant\033[0m")
        print("\033[90m  Type 'help' for commands, 'exit' to quit\033[0m")
        print("\033[1;36m" + "─" * 50 + "\033[0m\n")

        while True:
            try:
                raw = input("\033[1;32msyntaxai\033[0m\033[90m>\033[0m ").strip()
            except KeyboardInterrupt:
                print()
                continue
            except EOFError:
                print("\nGoodbye!")
                break

            if not raw:
                continue

            cmd = raw.lower()
            if cmd in ("exit", "quit", "/quit"):
                print("Goodbye!")
                break
            if cmd in ("help", "/help"):
                self._print_help()
                continue
            if cmd == "/clear":
                self._messages.clear()
                print("\033[33m[context cleared]\033[0m")
                continue

            print("\033[90m[thinking...]\033[0m", end="\r")
            try:
                response = self.run(raw)
                print(" " * 20, end="\r")
                print(f"\n\033[0m{response}\033[0m\n")
            except Exception as e:
                print(f"\n\033[1;31mError: {e}\033[0m\n")

    def _print_help(self) -> None:
        """Print help information."""
        print("\n\033[1mCommands:\033[0m")
        for cmd, desc in [
            ("/help", "Show this help"),
            ("/clear", "Clear conversation context"),
            ("/model", "Show current model"),
            ("/quit", "Exit"),
            ("autofix <files>", "Auto-fix code issues"),
            ("refactor <files>", "Refactor code"),
            ("review <files>", "Review code"),
            ("test", "Run project tests"),
            ("analyze", "Analyze project structure"),
        ]:
            print(f"  \033[1;33m{cmd:<18}\033[0m {desc}")
        print()

    def get_current_model(self) -> str:
        """Return the current model name."""
        return self.model

    def get_available_models(self) -> list[str]:
        """Get list of available models from the provider."""
        try:
            with PiAgentSync(model=self.model) as agent:
                return agent.list_models()
        except Exception:
            return []

    def get_available_providers(self) -> list[str]:
        """Get list of available providers."""
        try:
            with PiAgentSync(model=self.model) as agent:
                return agent.list_providers()
        except Exception:
            return []
