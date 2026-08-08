"""Core agent loop logic for SyntaxAI."""

import os
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

from syntaxai.core.config import Config, ProviderType
from syntaxai.core.context import ContextManager, SkillContext
from syntaxai.providers.base import LLMProvider
from syntaxai.providers.gemini import GeminiProvider
from syntaxai.providers.deepseek import DeepSeekProvider
from syntaxai.providers.nemotron import NemotronProvider
from syntaxai.tools.fs_tools import (
    read_file, write_file, edit_file, list_tree,
    list_sensitive_files
)
from syntaxai.tools.shell_tools import execute_command
from syntaxai.tools.git_tools import git_status, git_diff, git_commit, git_push
from syntaxai.tools.skills_loader import load_skills, extract_skills_from_project
from syntaxai.safety.approval import get_approval, log_command
from syntaxai.safety.risk_rules import classify_command, RiskLevel


@dataclass
class ToolResult:
    success: bool
    output: str
    error: str = ""
    tool_used: str = ""


class Agent:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.load()
        self.context = ContextManager(self.config)
        self.provider: Optional[LLMProvider] = None
        self.tools: dict[str, Callable] = {
            "read_file": self._tool_read_file,
            "write_file": self._tool_write_file,
            "edit_file": self._tool_edit_file,
            "list_tree": self._tool_list_tree,
            "shell": self._tool_shell,
            "git_status": self._tool_git_status,
            "git_diff": self._tool_git_diff,
            "git_commit": self._tool_git_commit,
            "git_push": self._tool_git_push,
        }
        self._initialized_providers: dict[ProviderType, LLMProvider] = {}
        self._setup_initial_context()

    def _setup_initial_context(self) -> None:
        self.context.add_message(
            "system",
            "You are SyntaxAI, a terminal-based programming assistant AI. "
            "You can read, write, and edit files, execute shell commands, "
            "and interact with git/GitHub. Always ask for confirmation before "
            "executing potentially dangerous commands."
        )

    def _get_provider(self, task_complexity: str = "light") -> Optional[LLMProvider]:
        provider_type = self.config.get_active_provider()
        if not provider_type:
            return None

        cache_key = (provider_type.name, task_complexity)
        if cache_key in self._initialized_providers:
            return self._initialized_providers[cache_key]

        api_key = self.config.get_api_key(provider_type.name)
        if not api_key:
            print(f"Warning: No API key configured for {provider_type.name.value}")
            return None

        if provider_type.name == ProviderType.GEMINI:
            model_name = self.config.heavy_model if task_complexity == "heavy" else self.config.light_model
            provider = GeminiProvider(api_key=api_key, model=model_name)
        elif provider_type.name == ProviderType.DEEPSEEK:
            model_name = "deepseek-coder-v2-lite" if task_complexity == "light" else "deepseek-coder-v2"
            provider = DeepSeekProvider(api_key=api_key, model=model_name)
        elif provider_type.name == ProviderType.NEMOTRON:
            model_name = "nemotron-mini" if task_complexity == "light" else "nemotron-pro"
            provider = NemotronProvider(api_key=api_key, model=model_name)
        else:
            return None

        self._initialized_providers[cache_key] = provider
        return provider

    def _tool_read_file(self, args: dict) -> ToolResult:
        path = args.get("path", "")
        if not path:
            return ToolResult(False, "", "Path argument required")
        
        result = read_file(path)
        return ToolResult(
            success=result.success,
            output=result.content if result.success else "",
            error=result.error if not result.success else ""
        )

    def _tool_write_file(self, args: dict) -> ToolResult:
        path = args.get("path", "")
        content = args.get("content", "")
        if not path:
            return ToolResult(False, "", "Path argument required")
        
        result = write_file(path, content)
        return ToolResult(
            success=result.success,
            output=f"File written: {path}" if result.success else "",
            error=result.error if not result.success else ""
        )

    def _tool_edit_file(self, args: dict) -> ToolResult:
        path = args.get("path", "")
        old = args.get("old", "")
        new = args.get("new", "")
        if not path:
            return ToolResult(False, "", "Path argument required")
        
        result = edit_file(path, old, new)
        return ToolResult(
            success=result.success,
            output=f"File edited: {path}" if result.success else "",
            error=result.error if not result.success else ""
        )

    def _tool_list_tree(self, args: dict) -> ToolResult:
        path = args.get("path", ".")
        depth = args.get("depth", 3)
        
        tree_str = list_tree(path, depth)
        return ToolResult(True, tree_str)

    def _tool_shell(self, args: dict) -> ToolResult:
        command = args.get("command", "")
        cwd = args.get("cwd", None)
        
        if not command:
            return ToolResult(False, "", "Command argument required")
        
        result = execute_command(command, cwd)
        return ToolResult(
            success=result.success,
            output=result.stdout if result.stdout else "",
            error=result.stderr if result.stderr else ""
        )

    def _tool_git_status(self, args: dict) -> ToolResult:
        result = git_status()
        return ToolResult(True, result)

    def _tool_git_diff(self, args: dict) -> ToolResult:
        result = git_diff()
        return ToolResult(True, result)

    def _tool_git_commit(self, args: dict) -> ToolResult:
        message = args.get("message", "")
        if not message:
            return ToolResult(False, "", "Commit message required")
        
        result = git_commit(message)
        return ToolResult(True, result)

    def _tool_git_push(self, args: dict) -> ToolResult:
        remote = args.get("remote", "origin")
        branch = args.get("branch", "main")
        
        result = git_push(remote, branch)
        return ToolResult(True, result)

    def run(self, user_input: str) -> str:
        try:
            self.context.set_project_path(os.getcwd())
        except Exception:
            pass

        project_skills = extract_skills_from_project()
        for skill in project_skills:
            self.context.skills.append(skill)

        self.context.add_message("user", user_input)

        task_complexity = "light"
        if self.context.needs_heavy_model(user_input):
            task_complexity = "heavy"

        provider = self._get_provider(task_complexity)
        if not provider:
            return "Error: No LLM provider available. Please configure an API key."

        while True:
            try:
                response = provider.generate(
                    prompt=user_input,
                    context=self.context.get_context_string(),
                    tools=list(self.tools.keys()),
                    tool_descriptions=self._get_tool_descriptions()
                )

                if response.tool_calls:
                    self.context.add_message(
                        "assistant",
                        response.content or "",
                        tool_calls=response.tool_calls
                    )
                    
                    tool_name = response.tool_calls[0].get("name", "") if response.tool_calls else ""
                    tool_args = response.tool_calls[0].get("arguments", {}) if response.tool_calls else {}
                    
                    tool_result = self._execute_tool(tool_name, tool_args, user_input)
                    
                    if not tool_result.success:
                        return f"Tool execution failed: {tool_result.error}"
                    
                    self.context.add_message(
                        "tool",
                        tool_result.output,
                        tool_results=[{"tool": tool_name, "result": tool_result.output}]
                    )
                    user_input = f"Tool result: {tool_result.output}\nContinue or provide next instruction."
                else:
                    self.context.add_message("assistant", response.content or "")
                    return response.content or "No response received."

            except Exception as e:
                return f"Error during execution: {str(e)}"

    def _get_tool_descriptions(self) -> dict:
        return {
            "read_file": "Read file contents. Args: path",
            "write_file": "Write content to file. Args: path, content",
            "edit_file": "Edit file with diff. Args: path, old, new",
            "list_tree": "List directory tree. Args: path, depth",
            "shell": "Execute shell command with safety checks. Args: command, cwd",
            "git_status": "Get git status",
            "git_diff": "Get git diff",
            "git_commit": "Commit changes. Args: message",
            "git_push": "Push to remote. Args: remote, branch"
        }

    def _execute_tool(self, tool_name: str, args: dict, original_prompt: str) -> ToolResult:
        if tool_name not in self.tools:
            return ToolResult(False, "", f"Unknown tool: {tool_name}")

        tool_func = self.tools[tool_name]
        
        if tool_name in ["shell", "git_push", "git_commit"]:
            command_str = f"{tool_name} {json.dumps(args)}" if args else tool_name
            risk_level = classify_command(command_str)
            
            if risk_level == RiskLevel.HIGH:
                if not get_approval(command_str, "high", original_prompt):
                    return ToolResult(False, "", "Command execution cancelled by user.")
                log_command(command_str, "high", False, "", "")
            elif risk_level == RiskLevel.MEDIUM:
                if not get_approval(command_str, "medium", original_prompt):
                    return ToolResult(False, "", "Command execution cancelled by user.")
                log_command(command_str, "medium", True, "", "")

        try:
            return tool_func(args)
        except Exception as e:
            return ToolResult(False, "", str(e))

    def run_repl(self) -> None:
        print("SyntaxAI - Terminal Programming Assistant")
        print("Type 'exit' or 'quit' to exit, 'help' for commands\n")
        
        while True:
            try:
                user_input = input("syntaxai> ").strip()
                
                if user_input.lower() in ["exit", "quit"]:
                    break
                if user_input.lower() == "help":
                    self._show_help()
                    continue
                if not user_input:
                    continue

                response = self.run(user_input)
                print(f"\n{response}\n")

            except KeyboardInterrupt:
                print("\n")
                continue
            except EOFError:
                break

    def _show_help(self) -> None:
        help_text = """
Available commands:
  help      - Show this help
  exit      - Exit the REPL
  clear     - Clear conversation context
  project   - Show current project info
  skills    - List available skills

Available tools:
  read_file(path)    - Read file contents
  write_file(path, content) - Write to file
  edit_file(path, old, new) - Edit file
  list_tree(path, depth) - Directory tree
  shell(command)     - Execute shell command
  git_status         - Git status
  git_diff           - Git diff
  git_commit(msg)    - Commit changes
  git_push(remote, branch) - Push to remote
"""
        print(help_text)

    def clear_context(self) -> None:
        self.context.clear()
        print("Context cleared.")

    def show_project_info(self) -> None:
        path = Path.cwd()
        print(f"Current directory: {path}")
        
        skills = extract_skills_from_project()
        if skills:
            print(f"Available skills: {', '.join(s.name for s in skills)}")
        else:
            print("No skills found in project.")


def main():
    config = Config.load()
    agent = Agent(config)
    agent.run_repl()


if __name__ == "__main__":
    main()