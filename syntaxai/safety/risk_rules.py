"""Risk classification rules for commands."""

import re
from typing import Tuple
from syntaxai.safety.approval import RiskLevel


HIGH_RISK_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+\*",
    r"rm\s+.*--",
    r"mkfs",
    r"dd\s+if=",
    r":\(\)\s*:\{\|:\&\;\}",
    r"chmod\s+777\s+/",
    r"chmod\s+777\s+/\w",
    r"chown\s+.*\s+/dev/",
    r">/\s*/dev/sd",
    r"shutdown",
    r"reboot",
    r"kill\s+-9\s+\d",
    r"pkill\s+-9",
    r"yes\s+",
    r">>\s*/dev/",
    r"git\s+push\s+--force",
    r"git\s+push\s+--force-with-lease",
    r"sudo\s+rm",
]

MEDIUM_RISK_PATTERNS = [
    r"rm\s+[^-]",
    r"git\s+reset\s+--hard",
    r"pip\s+uninstall",
    r"npm\s+uninstall",
    r"npm\s+run\s+uninstall",
    r"yarn\s+remove",
    r"bundler\s+remove",
    r"apt\s+remove",
    r"apt\s+suspend",
    r"brew\s+uninstall",
    r"chmod\s+(?![7-9]\d\d\s+/)",
    r"chown\s+",
    r"curl\s+.*|\.sh",
    r"wget\s+.*|\.sh",
    r"git\s+commit\s+--amend",
    r"git\s+rebase\s+-i",
    r"git\s+clean\s+.*-d",
    r"docker\s+rm.*-f",
    r"docker\s+system\s+prune",
    r"terraform\s+destroy",
    r"pulumi\s+destroy",
    r"npm\s+install\s+-g",
    r"pip\s+install\s+-g",
]

SAFE_PATTERNS = [
    r"ls",
    r"cat\s+",
    r"pwd",
    r"echo\s+",
    r"clear",
    r"git\s+status",
    r"git\s+log",
    r"git\s+show",
    r"make\s+help",
    r"python\s+-m\s+venv",
    r"poetry\s+show",
    r"pip\s+list",
    r"npm\s+list",
    r"which\s+",
    r"where\s+is\s+",
    r"pwd",
    r"date",
    r"cal",
    r"hostname",
    r"whoami",
    r"id",
    r"uname",
]


def classify_command(command: str) -> RiskLevel:
    cmd_normalized = " ".join(command.split())
    
    for pattern in HIGH_RISK_PATTERNS:
        if re.search(pattern, cmd_normalized, re.IGNORECASE):
            return RiskLevel.HIGH
    
    for pattern in MEDIUM_RISK_PATTERNS:
        if re.search(pattern, cmd_normalized, re.IGNORECASE):
            return RiskLevel.MEDIUM
    
    for pattern in SAFE_PATTERNS:
        if re.search(pattern, cmd_normalized, re.IGNORECASE):
            return RiskLevel.SAFE
    
    if "&&" in cmd_normalized or "||" in cmd_normalized or ";" in cmd_normalized:
        chain_risks = []
        for subcmd in re.split(r"[;]+|&&|\|\|", cmd_normalized):
            subcmd = subcmd.strip()
            if subcmd:
                chain_risks.append(classify_command(subcmd))
        
        if RiskLevel.HIGH in chain_risks:
            return RiskLevel.HIGH
        if RiskLevel.MEDIUM in chain_risks:
            return RiskLevel.MEDIUM
        return RiskLevel.SAFE
    
    if command.strip().endswith("/"):
        return RiskLevel.HIGH
    
    if is_outside_project(command):
        return RiskLevel.HIGH
    
    return RiskLevel.MEDIUM


def is_outside_project(command: str) -> bool:
    project_markers = [".git", "package.json", "requirements.txt", "Cargo.toml", 
                       "pom.xml", "build.gradle", "go.mod", "pyproject.toml"]
    
    cwd = "."
    
    paths_in_command = re.findall(r'/[^\s|&;]+', command)
    
    safe_paths = [
        "/home/", "/data/", "/tmp/", 
        str(cwd),
        "~/.local", "~/.cache"
    ]
    
    for path in paths_in_command:
        is_safe = False
        for safe in safe_paths:
            if path.startswith(safe):
                is_safe = True
                break
        
        if not is_safe:
            return True
    
    return False


def get_risk_explanation(command: str) -> str:
    cmd_base = command.split()[0] if command.split() else ""
    
    explanations = {
        "rm": "File/directory deletion",
        "dd": "Data destruction tool",
        "mkfs": "Filesystem creation (destroys data)",
        "chmod": "Permission modification",
        "chown": "Ownership modification",
        "shutdown": "System shutdown",
        "reboot": "System reboot",
        "kill": "Process termination",
        "pkill": "Process termination by name",
        "git": "Git operations (commit, push, reset)",
        "curl": "Download/external content execution",
        "wget": "File download",
        "sudo": "Elevated privilege execution",
    }
    
    for key, expl in explanations.items():
        if key in command.lower():
            return expl
    
    if "&&" in command or ";" in command:
        return "Command chain - multiple operations"
    
    return "Unknown - requires approval"


def validate_command_composition(command: str) -> Tuple[bool, str]:
    if not command.strip():
        return False, "Empty command"
    
    dangerous_chains = [
        r"rm\s+.*&&.*rm",
        r"dd\s+.*&&.*rm",
        r"mkfs.*&&.*mount",
    ]
    
    for pattern in dangerous_chains:
        if re.search(pattern, command, re.IGNORECASE):
            return False, f"Dangerous command chain detected"
    
    return True, ""