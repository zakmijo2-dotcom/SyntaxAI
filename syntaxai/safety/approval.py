"""Safety and approval system for SyntaxAI."""

import os
import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RiskLevel(str, Enum):
    SAFE = "safe"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ApprovalResult:
    approved: bool
    reason: str


def get_approval(command: str, risk_level: str, context: str = "") -> bool:
    if risk_level == RiskLevel.SAFE.value:
        return True
    
    print(f"\n{'='*50}")
    print(f"⚠️  COMMAND REQUIRES APPROVAL ({risk_level.upper()} RISK)")
    print(f"{'='*50}")
    print(f"\nCommand: {command}")
    print(f"\nContext: {context[:100]}..." if len(context) > 100 else f"\nContext: {context}")
    
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
    
    print(f"\n{'='*50}")
    
    while True:
        response = input("\nDo you want to execute this command? (yes/no): ").strip().lower()
        
        if response in ["yes", "y"]:
            print("✓ Approved")
            return True
        elif response in ["no", "n", ""]:
            print("✗ Cancelled")
            return False
        else:
            print("Please type 'yes' or 'no'")


def log_command(command: str, risk_level: str, approved: bool, 
                stdout: str = "", stderr: str = "") -> None:
    try:
        config = Config.get_log_path() if 'Config' in globals() else Path.home() / ".syntaxai" / "logs"
        log_dir = Path(config)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "risk_level": risk_level,
            "approved": approved,
            "stdout": stdout[:500] if stdout else "",
            "stderr": stderr[:500] if stderr else ""
        }
        
        log_file = log_dir / f"commands_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    except Exception:
        pass


class Config:
    @staticmethod
    def get_log_path() -> Path:
        return Path.home() / ".syntaxai" / "logs"


def get_command_history(limit: int = 50) -> list[dict]:
    log_path = Config.get_log_path()
    if not log_path.exists():
        return []
    
    history = []
    today = datetime.now().strftime('%Y-%m-%d')
    log_file = log_path / f"commands_{today}.jsonl"
    
    if not log_file.exists():
        return []
    
    try:
        with open(log_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    history.append(entry)
                except json.JSONDecodeError:
                    continue
        
        return history[-limit:]
    except Exception:
        return []


def clear_command_history() -> str:
    log_path = Config.get_log_path()
    if not log_path.exists():
        return "No history to clear."
    
    cleared = 0
    for log_file in log_path.glob("commands_*.jsonl"):
        try:
            log_file.unlink()
            cleared += 1
        except Exception:
            pass
    
    return f"Cleared {cleared} log files."