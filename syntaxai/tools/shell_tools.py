"""Shell command tools for SyntaxAI — security-hardened implementation.

Key security improvements vs. the original:
- subprocess is invoked with a *list* of arguments (no shell=True) wherever
  possible, preventing command-injection via crafted strings.
- A hard blocklist rejects catastrophically destructive patterns before any
  approval or risk classification is attempted.
- Commands that *require* shell features (pipes, redirects, shell builtins) are
  run with shell=True **only** after the user explicitly approves them.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from syntaxai.safety.risk_rules import classify_command, RiskLevel
from syntaxai.safety.approval import get_approval, log_command
from syntaxai.tools.output import truncate_output

logger = logging.getLogger(__name__)

# Hard-blocked patterns — rejected unconditionally, no approval possible.
# These are catastrophic, irreversible operations that must never run, even
# with explicit user approval.
_HARD_BLOCKED: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\brm\s+-rf\s+/\s*$", re.IGNORECASE), "rm -rf / (filesystem root)"),
    (re.compile(r"\brm\s+-rf\s+/\*\s*$", re.IGNORECASE), "rm -rf /* (filesystem root)"),
    (re.compile(r"\brm\s+-rf\s+/[^a-zA-Z0-9]", re.IGNORECASE), "rm -rf /<root-path>"),
    (re.compile(r"\brm\s+--no-preserve-root", re.IGNORECASE), "--no-preserve-root"),
    (re.compile(r":\(\)\s*\{", re.IGNORECASE), "fork bomb"),
    (re.compile(r"\bmkfs\b", re.IGNORECASE), "filesystem creation (mkfs)"),
    (re.compile(r"\bdd\s+if=\s*/dev/", re.IGNORECASE), "raw disk overwrite via dd"),
    (re.compile(r">\s*/dev/(sd|hd|nvme|vda)", re.IGNORECASE), "overwrite of a block device"),
    (re.compile(r"\bshred\s+-[a-zA-Z]*[nuz]", re.IGNORECASE), "secure wipe (shred)"),
    (re.compile(r"\bchmod\s+-R\s+000\b", re.IGNORECASE), "recursive chmod 000"),
]

# Shell-feature indicators — requires shell=True
_NEEDS_SHELL_RE = re.compile(r"[|;&<>$`]|\beval\b|\bexec\b")


@dataclass
class CommandResult:
    success: bool
    stdout: str
    stderr: str
    command: str
    approved: bool = False
    exit_code: int = 0


def _is_hard_blocked(command: str) -> tuple[bool, str]:
    for pat, reason in _HARD_BLOCKED:
        if pat.search(command):
            return True, f"Blocked (hard deny): {reason}"
    return False, ""


def _needs_shell(command: str) -> bool:
    return bool(_NEEDS_SHELL_RE.search(command))


def execute_command(
    command: str, cwd: Optional[str] = None, timeout: int = 60
) -> CommandResult:
    """Execute *command* with the minimum necessary privileges.

    - Commands are run **without** ``shell=True`` when possible (no shell
      metacharacters), preventing injection attacks.
    - Commands with shell metacharacters (``|``, ``>``, ``$``, …) are run
      with ``shell=True`` but only after passing the full risk-approval flow.
    - All executions are logged.
    """
    command = command.strip()
    if not command:
        return CommandResult(False, "", "Empty command", command)

    # 1. Hard blocklist — unconditional rejection
    blocked, reason = _is_hard_blocked(command)
    if blocked:
        logger.warning("Hard-blocked command: %s — %s", command, reason)
        return CommandResult(False, "", reason, command)

    # 2. Risk classification & approval
    risk = classify_command(command)
    approved = False

    if risk == RiskLevel.HIGH:
        approved = get_approval(command, "high", f"Execute: {command}")
        if not approved:
            return CommandResult(False, "", "Cancelled by user (HIGH risk)", command)
    elif risk == RiskLevel.MEDIUM:
        approved = get_approval(command, "medium", f"Execute: {command}")
        if not approved:
            return CommandResult(False, "", "Cancelled by user (MEDIUM risk)", command)
    else:
        approved = True

    log_command(command, risk.value, approved, "", "")

    # 3. Determine working directory
    working_dir: Optional[str] = cwd or os.getcwd()
    if not Path(working_dir).is_dir():
        return CommandResult(
            False, "", f"Directory not found: {working_dir}", command, approved
        )

    # 4. Execute
    try:
        use_shell = _needs_shell(command)

        if use_shell:
            # shell=True required for pipes/redirects — command string passed as-is
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_dir,
                env=os.environ.copy(),
            )
        else:
            # Safe path: parse into a list, no shell expansion possible
            try:
                args = shlex.split(command)
            except ValueError as exc:
                return CommandResult(
                    False, "", f"Command parse error: {exc}", command, approved
                )
            proc = subprocess.run(
                args,
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_dir,
                env=os.environ.copy(),
            )

        return CommandResult(
            success=proc.returncode == 0,
            stdout=truncate_output(proc.stdout),
            stderr=truncate_output(proc.stderr),
            command=command,
            approved=approved,
            exit_code=proc.returncode,
        )

    except subprocess.TimeoutExpired:
        return CommandResult(
            False, "", f"Timed out after {timeout}s", command, approved
        )
    except FileNotFoundError as exc:
        return CommandResult(False, "", f"Command not found: {exc}", command, approved)
    except Exception as exc:
        logger.error("Command execution error: %s", exc)
        return CommandResult(False, "", str(exc), command, approved)


def check_permissions() -> dict:
    """Return a summary of the current process permissions."""
    return {
        "is_root": os.geteuid() == 0,
        "uid": os.geteuid(),
        "gid": os.getegid(),
        "home": str(Path.home()),
        "cwd": str(Path.cwd()),
        "cwd_writable": os.access(Path.cwd(), os.W_OK),
    }
