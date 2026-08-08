"""
Core agent loop for SyntaxAI.

Supports:
- Multi-tool execution per LLM response
- Iterative loop with configurable max_steps
- Per-tool retry with exponential back-off
- Automatic re-planning after tool failures
- Provider fallback when the primary provider is unavailable
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from syntaxai.core.config import Config, ProviderType
from syntaxai.core.context import ContextManager
from syntaxai.providers.base import LLMProvider, LLMResponse, ToolSchema
from syntaxai.providers.gemini import GeminiProvider
from syntaxai.providers.deepseek import DeepSeekProvider
from syntaxai.providers.nemotron import NemotronProvider
from syntaxai.tools.fs_tools import read_file, write_file, edit_file, list_tree
from syntaxai.tools.shell_tools import execute_command
from syntaxai.tools.git_tools import git_status, git_diff, git_commit, git_push
from syntaxai.tools.skills_loader import extract_skills_from_project
from syntaxai.safety.approval import get_approval, log_command
from syntaxai.safety.risk_rules import classify_command, RiskLevel

logger = logging.getLogger(__name__)

# ── constants ─────────────────────────────────────────────────────────────────
MAX_STEPS: int = 20          # hard stop for the agent loop
MAX_TOOL_RETRIES: int = 2    # retries per failed tool call
RETRY_DELAY: float = 0.5     # seconds between retries


# ── result types ──────────────────────────────────────────────────────────────
@dataclass
class ToolResult:
    success: bool
    output: str
    error: str = ""
    tool_used: str = ""
    retries: int = 0


@dataclass
class AgentStep:
    """One step in the agent loop (one LLM call + all its tool executions)."""
    step_num: int
    llm_response: Optional[LLMResponse] = None
    tool_results: list[ToolResult] = field(default_factory=list)
    final_text: str = ""
    error: str = ""


# ── tool schema registry ───────────────────────────────────────────────────────
TOOL_SCHEMAS: list[ToolSchema] = [
    ToolSchema(
        name="read_file",
        description="Read the contents of a file on disk.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative file path"},
            },
            "required": ["path"],
        },
    ),
    ToolSchema(
        name="write_file",
        description="Create or overwrite a file with the given content.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to write"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    ),
    ToolSchema(
        name="edit_file",
        description="Replace a specific substring in a file (diff-style, not full overwrite).",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to edit"},
                "old": {"type": "string", "description": "Exact text to replace"},
                "new": {"type": "string", "description": "Replacement text"},
            },
            "required": ["path", "old", "new"],
        },
    ),
    ToolSchema(
        name="list_tree",
        description="List the directory tree up to a given depth.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path (default: '.')"},
                "depth": {"type": "integer", "description": "Tree depth, 1-10 (default: 3)"},
            },
            "required": [],
        },
    ),
    ToolSchema(
        name="shell",
        description="Execute a shell command. Dangerous commands require user approval.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
                "cwd": {"type": "string", "description": "Working directory (optional)"},
            },
            "required": ["command"],
        },
    ),
    ToolSchema(
        name="git_status",
        description="Return the current git repository status.",
        parameters={"type": "object", "properties": {}, "required": []},
    ),
    ToolSchema(
        name="git_diff",
        description="Return the current git diff.",
        parameters={"type": "object", "properties": {}, "required": []},
    ),
    ToolSchema(
        name="git_commit",
        description="Stage all changes and create a git commit.",
        parameters={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Commit message"},
            },
            "required": ["message"],
        },
    ),
    ToolSchema(
        name="git_push",
        description="Push committed changes to a remote repository.",
        parameters={
            "type": "object",
            "properties": {
                "remote": {"type": "string", "description": "Remote name (default: origin)"},
                "branch": {"type": "string", "description": "Branch name (default: main)"},
            },
            "required": [],
        },
    ),
]


# ── agent ──────────────────────────────────────────────────────────────────────
class Agent:
    """Main SyntaxAI agent that orchestrates LLM calls and tool execution."""

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config.load()
        self.context = ContextManager(self.config)
        self._tool_handlers: dict[str, Callable[[dict], ToolResult]] = {
            "read_file":  self._handle_read_file,
            "write_file": self._handle_write_file,
            "edit_file":  self._handle_edit_file,
            "list_tree":  self._handle_list_tree,
            "shell":      self._handle_shell,
            "git_status": self._handle_git_status,
            "git_diff":   self._handle_git_diff,
            "git_commit": self._handle_git_commit,
            "git_push":   self._handle_git_push,
        }
        self._provider_cache: dict[tuple, LLMProvider] = {}
        self._provider_order: list[ProviderType] = self._build_provider_order()
        self._init_system_context()

    # ── context & setup ────────────────────────────────────────────────────────
    def _init_system_context(self) -> None:
        self.context.add_message(
            "system",
            "You are SyntaxAI, a terminal-based programming assistant.\n"
            "You have access to tools for reading/writing files, running shell commands, "
            "and interacting with git. Use them as needed.\n"
            "Always explain what you are doing and why before calling a tool.\n"
            "If a tool fails, analyse the error and try a different approach.\n"
            "Never execute destructive commands without explicit user confirmation.",
        )

    def _build_provider_order(self) -> list[ProviderType]:
        """Return providers sorted so the configured default comes first."""
        all_providers = list(ProviderType)
        default = self.config.default_provider
        return [default] + [p for p in all_providers if p != default]

    # ── provider management ────────────────────────────────────────────────────
    def _get_provider(self, complexity: str = "light") -> Optional[LLMProvider]:
        """Return a working provider, trying fallbacks if the primary fails."""
        for pt in self._provider_order:
            provider = self._init_provider(pt, complexity)
            if provider is not None:
                return provider
        return None

    def _init_provider(
        self, pt: ProviderType, complexity: str
    ) -> Optional[LLMProvider]:
        cache_key = (pt, complexity)
        if cache_key in self._provider_cache:
            return self._provider_cache[cache_key]

        api_key = self.config.get_api_key(pt)
        if not api_key:
            return None

        try:
            provider: LLMProvider
            if pt == ProviderType.GEMINI:
                model = (
                    self.config.heavy_model
                    if complexity == "heavy"
                    else self.config.light_model
                )
                provider = GeminiProvider(api_key=api_key, model=model)
            elif pt == ProviderType.DEEPSEEK:
                model = (
                    "deepseek-chat"
                    if complexity == "light"
                    else "deepseek-reasoner"
                )
                provider = DeepSeekProvider(api_key=api_key, model=model)
            elif pt == ProviderType.NEMOTRON:
                model = (
                    "nvidia/nemotron-mini-4b-instruct"
                    if complexity == "light"
                    else "nvidia/llama-3.1-nemotron-70b-instruct"
                )
                provider = NemotronProvider(api_key=api_key, model=model)
            else:
                return None

            self._provider_cache[cache_key] = provider
            return provider
        except Exception as exc:
            logger.warning("Failed to initialise provider %s: %s", pt, exc)
            return None

    # ── main run loop ──────────────────────────────────────────────────────────
    def run(self, user_input: str, *, max_steps: int = MAX_STEPS) -> str:
        """
        Run the agent loop for *user_input*.

        Returns the final assistant reply as a plain string.
        The loop terminates when:
          - the LLM returns a response with no tool calls (done), or
          - max_steps is reached.
        """
        # refresh project context
        try:
            self.context.set_project_path(os.getcwd())
        except Exception:
            pass

        # load skills
        for skill in extract_skills_from_project():
            if skill not in self.context.skills:
                self.context.skills.append(skill)

        self.context.add_message("user", user_input)

        complexity = "heavy" if self.context.needs_heavy_model(user_input) else "light"
        provider = self._get_provider(complexity)
        if provider is None:
            return (
                "No LLM provider is available. "
                "Run `syntaxai --setup-api` to configure an API key."
            )

        history = self.context.get_messages_for_provider()
        last_error: str = ""

        for step_num in range(1, max_steps + 1):
            try:
                response = provider.generate(
                    messages=history,
                    tool_schemas=TOOL_SCHEMAS,
                )
            except Exception as exc:
                last_error = str(exc)
                logger.error("LLM call failed at step %d: %s", step_num, exc)
                break

            # ── no tool calls → final answer ──────────────────────────────────
            if not response.tool_calls:
                answer = response.content or ""
                self.context.add_message("assistant", answer)
                return answer

            # ── execute every tool call the LLM requested ─────────────────────
            self.context.add_message(
                "assistant",
                response.content or "",
                tool_calls=response.tool_calls,
            )

            tool_result_messages: list[dict] = []
            any_failure = False

            for call in response.tool_calls:
                name = call.get("name", "")
                args = call.get("arguments", {})
                call_id = call.get("id", name)

                result = self._dispatch_tool(name, args, user_input)

                if not result.success:
                    any_failure = True

                tool_result_messages.append({
                    "tool_call_id": call_id,
                    "role": "tool",
                    "name": name,
                    "content": result.output if result.success else f"ERROR: {result.error}",
                })

                self.context.add_message(
                    "tool",
                    result.output if result.success else f"ERROR: {result.error}",
                    tool_results=[{"tool": name, "result": result.output, "error": result.error}],
                )

            # append tool results to provider history
            history = self.context.get_messages_for_provider()

            # if all tools failed, inject a re-planning hint
            if any_failure and step_num < max_steps:
                history.append({
                    "role": "user",
                    "content": (
                        "One or more tools failed. Review the errors above, "
                        "adapt your plan, and continue."
                    ),
                })

        # loop exhausted without a final answer
        if last_error:
            return f"Agent stopped after error: {last_error}"
        return (
            f"Agent reached maximum steps ({max_steps}) without a final answer. "
            "Try a more specific request."
        )

    # ── tool dispatch & retry ──────────────────────────────────────────────────
    def _dispatch_tool(
        self, name: str, args: dict, original_prompt: str
    ) -> ToolResult:
        """Call the tool *name* with retry logic."""
        if name not in self._tool_handlers:
            return ToolResult(False, "", f"Unknown tool: {name!r}", name)

        handler = self._tool_handlers[name]
        last_result = ToolResult(False, "", "Not executed", name)

        for attempt in range(MAX_TOOL_RETRIES + 1):
            if attempt > 0:
                time.sleep(RETRY_DELAY * attempt)
                logger.debug("Retrying tool %s (attempt %d)", name, attempt + 1)

            try:
                result = handler(args)
                result.tool_used = name
                result.retries = attempt
                if result.success:
                    return result
                last_result = result
            except Exception as exc:
                last_result = ToolResult(False, "", str(exc), name, attempt)

        return last_result

    # ── individual tool handlers ───────────────────────────────────────────────
    def _handle_read_file(self, args: dict) -> ToolResult:
        path = args.get("path", "")
        if not path:
            return ToolResult(False, "", "Missing required argument: path")
        r = read_file(path)
        return ToolResult(r.success, r.content if r.success else "", r.error if not r.success else "")

    def _handle_write_file(self, args: dict) -> ToolResult:
        path = args.get("path", "")
        content = args.get("content", "")
        if not path:
            return ToolResult(False, "", "Missing required argument: path")
        r = write_file(path, content)
        return ToolResult(r.success, f"Written: {path}" if r.success else "", r.error)

    def _handle_edit_file(self, args: dict) -> ToolResult:
        path = args.get("path", "")
        old = args.get("old", "")
        new = args.get("new", "")
        if not path:
            return ToolResult(False, "", "Missing required argument: path")
        r = edit_file(path, old, new)
        return ToolResult(r.success, f"Edited: {path}" if r.success else "", r.error)

    def _handle_list_tree(self, args: dict) -> ToolResult:
        path = args.get("path", ".")
        depth = int(args.get("depth", 3))
        return ToolResult(True, list_tree(path, depth))

    def _handle_shell(self, args: dict) -> ToolResult:
        command = args.get("command", "")
        cwd = args.get("cwd") or None
        if not command:
            return ToolResult(False, "", "Missing required argument: command")
        r = execute_command(command, cwd)
        combined = "\n".join(filter(None, [r.stdout, r.stderr]))
        return ToolResult(r.success, combined, r.stderr if not r.success else "")

    def _handle_git_status(self, _args: dict) -> ToolResult:
        return ToolResult(True, git_status())

    def _handle_git_diff(self, _args: dict) -> ToolResult:
        return ToolResult(True, git_diff())

    def _handle_git_commit(self, args: dict) -> ToolResult:
        message = args.get("message", "")
        if not message:
            return ToolResult(False, "", "Missing required argument: message")
        result = git_commit(message)
        return ToolResult(True, result)

    def _handle_git_push(self, args: dict) -> ToolResult:
        remote = args.get("remote", "origin")
        branch = args.get("branch", "main")
        result = git_push(remote, branch)
        return ToolResult(True, result)

    # ── REPL ───────────────────────────────────────────────────────────────────
    def run_repl(self) -> None:
        """Interactive REPL with readline history and rich output."""
        self._setup_readline()
        self._print_banner()

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
            if cmd in ("clear", "/clear"):
                self.context.clear()
                self._init_system_context()
                print("\033[33m[context cleared]\033[0m")
                continue
            if cmd in ("project", "/project"):
                self._print_project_info()
                continue
            if cmd in ("skills", "/skills"):
                self._print_skills()
                continue

            # normal query
            print("\033[90m[thinking…]\033[0m", end="\r")
            try:
                response = self.run(raw)
            except Exception as exc:
                self._print_error(str(exc))
                continue

            print(" " * 20, end="\r")  # clear "thinking…"
            print(f"\n\033[0m{response}\033[0m\n")

    # ── REPL helpers ───────────────────────────────────────────────────────────
    @staticmethod
    def _setup_readline() -> None:
        try:
            import readline
            import atexit

            history_file = Path.home() / ".syntaxai" / "history"
            history_file.parent.mkdir(parents=True, exist_ok=True)

            try:
                readline.read_history_file(history_file)
            except FileNotFoundError:
                pass

            readline.set_history_length(500)
            atexit.register(readline.write_history_file, history_file)
        except ImportError:
            pass  # readline not available on Windows

    @staticmethod
    def _print_banner() -> None:
        print("\033[1;36m" + "─" * 50 + "\033[0m")
        print("\033[1;36m  SyntaxAI — Terminal AI Programming Assistant\033[0m")
        print("\033[90m  Type 'help' for commands, 'exit' to quit\033[0m")
        print("\033[1;36m" + "─" * 50 + "\033[0m\n")

    @staticmethod
    def _print_help() -> None:
        print("\n\033[1mCommands:\033[0m")
        for cmd, desc in [
            ("/help", "Show this help"),
            ("/clear", "Clear conversation context"),
            ("/project", "Show current project information"),
            ("/skills", "List loaded skills"),
            ("/quit", "Exit"),
        ]:
            print(f"  \033[1;33m{cmd:<12}\033[0m {desc}")

        print("\n\033[1mAvailable Tools:\033[0m")
        for s in TOOL_SCHEMAS:
            print(f"  \033[1;32m{s.name:<14}\033[0m {s.description}")
        print()

    @staticmethod
    def _print_error(msg: str) -> None:
        print(f"\n\033[1;31mError:\033[0m {msg}\n")

    def _print_project_info(self) -> None:
        cwd = Path.cwd()
        print(f"\n\033[1mDirectory:\033[0m {cwd}")
        skills = extract_skills_from_project()
        if skills:
            print(f"\033[1mSkills:\033[0m {', '.join(s.name for s in skills)}")
        else:
            print("\033[90mNo skills found in .skills/ directory\033[0m")
        print()

    def _print_skills(self) -> None:
        skills = extract_skills_from_project()
        if not skills:
            print("\033[90mNo skills found.\033[0m\n")
            return
        print("\n\033[1mLoaded Skills:\033[0m")
        for s in skills:
            triggers = ", ".join(s.triggers) if s.triggers else "—"
            print(f"  \033[1;32m{s.name:<20}\033[0m triggers: {triggers}")
        print()
