"""Safety and approval system for SyntaxAI."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path


class RiskLevel(str, Enum):
    SAFE = "safe"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ApprovalResult:
    approved: bool
    reason: str


_APPROVAL_CALLBACK: Callable[[str, str, str], bool] | None = None


def set_approval_callback(cb: Callable[[str, str, str], bool] | None) -> None:
    global _APPROVAL_CALLBACK
    _APPROVAL_CALLBACK = cb


def get_approval(
    tool_name: str,
    arguments: dict,
    risk_level: str,
    context: str = ""
) -> bool:
    """Ask the user (or the installed callback) to approve tool execution."""
    if risk_level == RiskLevel.SAFE.value:
        return True

    if _APPROVAL_CALLBACK is not None:
        return _APPROVAL_CALLBACK(tool_name, json.dumps(arguments), risk_level)

    if not sys.stdin.isatty():
        print(
            f"\n[auto-denied] {risk_level.upper()} command requires approval "
            f"but no interactive terminal is available:\n  {tool_name}"
        )
        return False

    print(f"\n{'=' * 50}")
    print(f"⚠️  COMMAND REQUIRES APPROVAL ({risk_level.upper()} RISK)")
    print(f"{'=' * 50}")
    print(f"\nTool: {tool_name}")
    print(f"Arguments: {arguments}")
    if context:
        preview = context[:200] + ("…" if len(context) > 200 else "")
        print(f"\nContext: {preview}")

    if risk_level == RiskLevel.MEDIUM.value:
        print("\nThis tool may have moderate effects:")
        print("  - Modify files or project state")
        print("  - Install packages or dependencies")
    elif risk_level == RiskLevel.HIGH.value:
        print("\n⚠️  THIS IS A HIGH-RISK TOOL!")
        print("Potential consequences:")
        print("  - Delete files permanently")
        print("  - Modify system configuration")

    print(f"\n{'=' * 50}")

    while True:
        try:
            response = input("\nDo you want to execute this tool? (yes/no): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n✗ Cancelled")
            return False

        if response in ["yes", "y"]:
            print("✓ Approved")
            return True
        elif response in ["no", "n", ""]:
            print("✗ Cancelled")
            return False
        else:
            print("Please type 'yes' or 'no'")


def log_path() -> Path:
    base = os.environ.get("SYNTAXAI_HOME")
    if base:
        return Path(base) / "logs"
    return Path.home() / ".syntaxai" / "logs"


def log_command(
    command: str,
    risk_level: str,
    approved: bool,
    stdout: str = "",
    stderr: str = "",
) -> None:
    try:
        log_dir = log_path()
        log_dir.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "command": command,
            "risk_level": risk_level,
            "approved": approved,
            "stdout": stdout[:500] if stdout else "",
            "stderr": stderr[:500] if stderr else "",
        }
        log_file = log_dir / f"commands_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def get_command_history(limit: int = 50) -> list[dict]:
    log_dir = log_path()
    if not log_dir.exists():
        return []

    history: list[dict] = []
    log_file = log_dir / f"commands_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    if not log_file.exists():
        return []

    try:
        with open(log_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    history.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return history[-limit:]
    except Exception:
        return []


def clear_command_history() -> str:
    log_dir = log_path()
    if not log_dir.exists():
        return "No history to clear."

    cleared = 0
    for log_file in log_dir.glob("commands_*.jsonl"):
        try:
            log_file.unlink()
            cleared += 1
        except Exception:
            pass

    return f"Cleared {cleared} log files."
