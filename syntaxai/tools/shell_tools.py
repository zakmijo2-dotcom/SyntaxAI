"""Shell command tools for SyntaxAI with safety checks."""

import os
import subprocess
import shlex
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from syntaxai.safety.risk_rules import classify_command, RiskLevel
from syntaxai.safety.approval import get_approval, log_command


@dataclass
class CommandResult:
    success: bool
    stdout: str
    stderr: str
    command: str
    approved: bool = False


BLOCKED_COMMANDS = {
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if="
}


def validate_command(command: str) -> tuple[bool, str]:
    cmd_lower = command.lower().strip()
    
    for blocked in BLOCKED_COMMANDS:
        if blocked.lower() in cmd_lower:
            return False, f"Blocked command detected: {blocked}"
    
    dangerous_patterns = [
        "mkfs", "dd if=", "> /dev/sd", "> /dev/hd",
        ":(){:|:&};:", "chmod -R 777",
    ]
    
    for pattern in dangerous_patterns:
        if pattern in cmd_lower:
            return False, f"Dangerous pattern detected: {pattern}"
    
    return True, ""


def execute_command(command: str, cwd: Optional[str] = None) -> CommandResult:
    if not command.strip():
        return CommandResult(False, "", "Empty command", "")

    valid, error_msg = validate_command(command)
    if not valid:
        return CommandResult(False, "", error_msg, command, False)

    risk_level = classify_command(command)
    approved = False

    if risk_level == RiskLevel.HIGH:
        approved = get_approval(command, "high", f"Execute shell command: {command}")
        if not approved:
            return CommandResult(False, "", "Command cancelled by user", command, False)
    elif risk_level == RiskLevel.MEDIUM:
        approved = get_approval(command, "medium", f"Execute shell command: {command}")
        if not approved:
            return CommandResult(False, "", "Command cancelled by user", command, False)
    else:
        approved = True

    log_command(command, risk_level.value, approved, "", "")

    try:
        working_dir = cwd if cwd else os.getcwd()
        
        if not Path(working_dir).exists():
            return CommandResult(False, "", f"Directory not found: {working_dir}", command, approved)

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=working_dir,
            env=dict(os.environ)
        )

        return CommandResult(
            success=result.returncode == 0,
            stdout=result.stdout,
            stderr=result.stderr,
            command=command,
            approved=approved
        )

    except subprocess.TimeoutExpired:
        return CommandResult(False, "", "Command timed out (60s limit)", command, approved)
    except Exception as e:
        return CommandResult(False, "", str(e), command, approved)


def execute_with_approval(command: str, cwd: Optional[str] = None) -> CommandResult:
    risk_level = classify_command(command)
    
    if risk_level == RiskLevel.HIGH:
        explanation = explain_risk(command)
        print(f"\n⚠️  HIGH RISK COMMAND:")
        print(f"   Command: {command}")
        print(f"   Risk: {explanation}")
        print("\nThis command may:\n" + "\n".join(f"   - {line}" for line in explanation.split(". ") if line))
        
        while True:
            response = input("\nType 'yes' to execute, or press Enter to cancel: ").strip().lower()
            if response == "yes":
                result = execute_command(command, cwd)
                result.approved = True
                return result
            elif response == "":
                return CommandResult(False, "", "Cancelled", command, False)

    return execute_command(command, cwd)


def explain_risk(command: str) -> str:
    cmd_base = command.split()[0] if command.split() else ""
    cmd_args = " ".join(command.split()[1:]) if len(command.split()) > 1 else ""
    
    explanations = {
        "rm": f"Removes files/directories. Arguments: {cmd_args}",
        "dd": "Creates/destroys data, can wipe entire disks",
        "mkfs": "Creates filesystem, destroys existing data",
        "chmod": f"Changes permissions. Arguments: {cmd_args}",
        "chown": f"Changes ownership. Arguments: {cmd_args}",
        "curl": f"Downloads/transfers data. Arguments: {cmd_args}",
        "wget": f"Downloads files. Arguments: {cmd_args}",
        "git": "Git operations including push, reset, rebase",
        "shutdown": "System shutdown or reboot",
        "reboot": "System reboot",
        "kill": f"Processes to kill. Arguments: {cmd_args}",
        "pkill": "Kill processes by name",
        "yes": "Command flood that can consume resources",
        ":(){": "Fork bomb - can crash the system",
        "sudo": "Elevated privileges command",
    }
    
    for key, explanation in explanations.items():
        if key in command.lower():
            return explanation
    
    return "Potentially destructive operation"


def run_in_background(command: str, description: str = "") -> CommandResult:
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True
        )
        return CommandResult(True, f"Started with PID: {process.pid}", "", f"bg:{command}", True)
    except Exception as e:
        return CommandResult(False, "", str(e), command, False)


def check_permissions() -> dict:
    return {
        "is_root": os.geteuid() == 0,
        "current_uid": os.geteuid(),
        "current_gid": os.getegid(),
        "home": str(Path.home()),
        "cwd": str(Path.cwd()),
        "has_write_access": os.access(Path.cwd(), os.W_OK)
    }