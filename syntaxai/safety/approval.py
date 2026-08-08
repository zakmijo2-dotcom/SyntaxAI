"""Safety and approval system for SyntaxAI."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional


class RiskLevel(str, Enum):
    SAFE = "safe"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ApprovalResult:
    approved: bool
    reason: str


# Optional callback used when running non-interactively (Web UI, tests, CI).
# Signature: (command, risk_level, context) -> bool
_APPROVAL_CALLBACK: Optional[Callable[[str, str, str], bool]] = None


def set_approval_callback(cb: Optional[Callable[[str, str, str], bool]]) -> None:
    """Install a custom approval handler (used by the Web UI and tests)."""
    global _APPROVAL_CALLBACK
    _APPROVAL_CALLBACK = cb


def get_approval(command: str, risk_level: str, context: str = "") -> bool:
    """Ask the user (or the installed callback) to approve *command*.

    SAFE commands are always auto-approved. MEDIUM/HIGH require either an
    interactive ``yes/no`` confirmation or the verdict of the installed
    approval callback.
    """
    if risk_level == RiskLevel.SAFE.value:
        return True

    if _APPROVAL_CALLBACK is not None:
        return _APPROVAL_CALLBACK(command, risk_level, context)

    # Non-interactive environments (piped input, no TTY) → deny by default.
    if not sys.stdin.isatty():
        print(
            f"\n[auto-denied] {risk_level.upper()} command requires approval "
            f"but no interactive terminal is available:\n  {command}"
        )
        return False

    print(f"\n{'=' * 50}")
    print(f"⚠️  COMMAND REQUIRES APPROVAL ({risk_level.upper()} RISK)")
    print(f"{'=' * 50}")
    print(f"\nCommand: {command}")
    if context:
        preview = context[:200] + ("…" if len(context) > 200 else "")
        print(f"\nContext: {preview}")

    if risk_level == RiskLevel.MEDIUM.value:
        print("\nThis command may have moderate effects:")
        print("  - Modify files or project state")
        print("  - Install packages or dependencies")
        print("  - Make commits or push changes")
    elif risk_level == RiskLevel.HIGH.value:
        print("\n⚠️  THIS IS A HIGH-RISK COMMAND!")
        print("Potential consequences:")
        print("  - Delete files permanently")
        print("  - Push destructive changes")
        print("  - Modify system configuration")
        print("  - Execute commands outside project directory")

    print(f"\n{'=' * 50}")

    while True:
        try:
            response = input("\nDo you want to execute this command? (yes/no): ").strip().lower()
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
    """Append an audit entry for *command* to the daily JSONL log."""
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
        # Logging must never break command execution.
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
