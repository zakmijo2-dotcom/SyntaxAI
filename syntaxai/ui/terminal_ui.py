"""Terminal UI for SyntaxAI."""

from typing import Optional
from datetime import datetime


class TerminalUI:
    def __init__(self, color: bool = True):
        self.color = color
        self.colors = {
            "reset": "\033[0m",
            "bold": "\033[1m",
            "red": "\033[91m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "blue": "\033[94m",
            "magenta": "\033[95m",
            "cyan": "\033[96m",
        }

    def colorize(self, text: str, color: str) -> str:
        if not self.color:
            return text
        return f"{self.colors.get(color, '')}{text}{self.colors['reset']}"

    def print_header(self, text: str) -> None:
        print(f"\n{self.colorize('=' * 50, 'cyan')}")
        print(self.colorize(f"  {text}", 'bold'))
        print(f"{self.colorize('=' * 50, 'cyan')}\n")

    def print_success(self, text: str) -> None:
        print(self.colorize(f"✓ {text}", 'green'))

    def print_error(self, text: str) -> None:
        print(self.colorize(f"✗ {text}", 'red'))

    def print_warning(self, text: str) -> None:
        print(self.colorize(f"⚠ {text}", 'yellow'))

    def print_info(self, text: str) -> None:
        print(self.colorize(f"ℹ {text}", 'blue'))

    def print_tool_result(self, tool_name: str, output: str, success: bool = True) -> None:
        color = 'green' if success else 'red'
        icon = "✓" if success else "✗"
        print(f"\n{self.colorize(f'{icon} {tool_name}', color)}")
        if output:
            print(f"  {output[:500]}")

    def print_context(self, context: str, max_lines: int = 10) -> None:
        lines = context.split("\n")
        if len(lines) > max_lines:
            print(self.colorize(f"... ({len(lines)} total lines)", 'yellow'))
            lines = lines[:max_lines]
        
        for line in lines:
            print(f"  {line}")

    def print_risk_warning(self, risk_level: str, explanation: str = "") -> None:
        warning = self.colorize(f"⚠ HIGH RISK: {risk_level}", 'red')
        print(f"\n{warning}")
        if explanation:
            print(f"  Reason: {explanation}")

    def print_thinking(self) -> None:
        print(self.colorize("\nAssistant is thinking...", 'yellow'), end="", flush=True)

    def print_thinking_done(self) -> None:
        print(self.colorize(" done\n", 'yellow'), end="", flush=True)

    def prompt_user(self, prompt_text: str) -> str:
        return input(self.colorize(f"\n{prompt_text} ", 'magenta'))

    def print_tool_usage(self, bytes_read: int, bytes_written: int = 0) -> None:
        if bytes_read > 0 or bytes_written > 0:
            print(self.colorize(f"  I/O: {bytes_written // 1024}KB written, {bytes_read // 1024}KB read", 'cyan'))

    def print_log_summary(self, log_path: str) -> None:
        print(self.colorize(f"\nCommand log saved to: {log_path}", 'blue'))


def create_simple_ui() -> TerminalUI:
    return TerminalUI(color=True)


def print_banner() -> None:
    banner = r"""
   _____ __  __                 _       _ 
  |  ___|  \/  | ___ _ __   __ _| |_ ___| |
  | |_  | |\/| |/ _ \ '_ \ / _` | __/ _ \ |
  |  _| | |  | |  __/ | | | (_| | ||  __/ |
  |_|   |_|  |_|\___|_| |_|\__,_|\__\___|_|
                                            
    Terminal AI Programming Assistant
    """
    ui = TerminalUI()
    print(ui.colorize(banner, 'magenta'))
    print(ui.colorize("Type 'help' for commands, 'exit' to quit", 'cyan'))