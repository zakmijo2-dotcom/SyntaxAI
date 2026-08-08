"""Risk classification rules for commands.

Design goals
------------
* Deterministic, well-tested classification into SAFE / MEDIUM / HIGH.
* Never use "path lives outside the project" as a proxy for "dangerous": that
  previous heuristic forced *every* command touching an absolute path to HIGH,
  which both annoyed users and masked real risks.  Instead we validate safety
  by inspecting the *command semantics* (delete, overwrite, network, sudo, …).
* Provide a clear human-readable explanation for every classification.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Tuple

from syntaxai.safety.approval import RiskLevel


# ── HIGH risk: data loss / system integrity / privilege / network egress ──────
HIGH_RISK_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+(-[a-zA-Z]*r|-{2}recursive)", "Recursive deletion (rm -r/--recursive)"),
    (r"\brm\s+.*-[a-zA-Z]*f", "Force deletion (rm -f)"),
    (r"\brm\s+-rf\b", "Recursive force deletion (rm -rf)"),
    (r"\brm\s+.*\s/\s*$", "Deletion targeting filesystem root"),
    (r"\brm\s+-\w*\s+/\S", "Deletion of an absolute root path"),
    (r"\bmkfs\b", "Filesystem creation (destroys all data)"),
    (r"\bdd\s+if=", "Raw disk/image overwrite (dd)"),
    (r":\(\)\s*\{.*\};:", "Fork bomb"),
    (r">\s*/dev/sd[a-z]", "Overwrite of a raw block device"),
    (r"\bdd\s+if=/dev/[a-z]", "Reading raw device into a command"),
    (r"\bchmod\s+777\s", "World-writable permissions (chmod 777)"),
    (r"\bchmod\s+-R\s+777", "Recursive world-writable permissions"),
    (r"\bchown\s+.*\s+/", "Ownership change on system path"),
    (r"\bchown\s+-R", "Recursive ownership change"),
    (r"\bshutdown\b", "System shutdown"),
    (r"\breboot\b", "System reboot"),
    (r"\bhalt\b", "System halt"),
    (r"\bpoweroff\b", "System power-off"),
    (r"\bkill\s+-9\b", "Forced process termination (SIGKILL)"),
    (r"\bpkill\s+-9\b", "Forced process kill by name"),
    (r"\bkillall\b", "Kill processes by name"),
    (r"\bsudo\b", "Elevated privilege execution (sudo)"),
    (r"\bsu\b", "Switch user / privilege escalation"),
    (r"\bgit\s+push\s+(--force|-f)\b", "Force push (rewrites remote history)"),
    (r"\bgit\s+push\s+.*--force-with-lease", "Force push with lease"),
    (r"\bgit\s+reset\s+--hard", "Hard reset (discards working tree)"),
    (r"\bgit\s+checkout\s+.*--\s+\.", "Discard all local changes via checkout"),
    (r"\bgit\s+clean\s+-[a-zA-Z]*[fd]", "Remove untracked files/directories (git clean)"),
    (r"\bgit\s+branch\s+-[a-zA-Z]*[Dd]", "Delete a branch (git branch -D)"),
    (r"\bdocker\s+system\s+prune", "Remove all unused docker data"),
    (r"\bdocker\s+rmi\b", "Delete docker images"),
    (r"\bterraform\s+destroy\b", "Destroy infrastructure (terraform)"),
    (r"\bpulumi\s+destroy\b", "Destroy infrastructure (pulumi)"),
    (r"\bcurl\b.*\|\s*(sudo\s+)?(ba)?sh\b", "Pipe download directly into a shell"),
    (r"\bwget\b.*\|\s*(sudo\s+)?(ba)?sh\b", "Pipe download directly into a shell"),
    (r"\bnpm\s+install\s+-g\b", "Global package install (affects whole system)"),
    (r"\bpip\s+install\s+-g\b", "Global package install"),
    (r"\bsystemctl\s+(stop|disable|restart)", "Service control via systemctl"),
    (r"\bcrontab\s+-r\b", "Remove all cron jobs"),
]


# ── MEDIUM risk: state-changing but recoverable / package changes ─────────────
MEDIUM_RISK_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+(?!-)", "File/directory deletion"),
    (r"\bgit\s+commit\b", "Create a commit"),
    (r"\bgit\s+commit\s+--amend", "Amend last commit (rewrites history)"),
    (r"\bgit\s+rebase\b", "Rebase (rewrites history)"),
    (r"\bgit\s+merge\b", "Merge branches"),
    (r"\bgit\s+push\b", "Push commits to remote"),
    (r"\bgit\s+checkout\b", "Switch branches/files"),
    (r"\bgit\s+stash\b", "Stash changes"),
    (r"\bgit\s+tag\b", "Create/delete a tag"),
    (r"\bpip\s+install\b", "Install Python packages"),
    (r"\bpip\s+uninstall\b", "Uninstall Python packages"),
    (r"\bnpm\s+install\b", "Install npm packages"),
    (r"\bnpm\s+uninstall\b", "Uninstall npm packages"),
    (r"\bnpm\s+run\b", "Run an npm script"),
    (r"\byarn\s+(add|remove)\b", "Modify yarn dependencies"),
    (r"\bapt\s+(install|remove|purge|upgrade)\b", "APT package management"),
    (r"\bbrew\s+(install|uninstall|upgrade)\b", "Homebrew package management"),
    (r"\bchmod\b", "Permission modification"),
    (r"\bchown\b", "Ownership modification"),
    (r"\bcurl\b", "Network download"),
    (r"\bwget\b", "Network download"),
    (r"\bscp\b", "Copy files over SSH"),
    (r"\brsync\b", "Synchronise files"),
    (r"\bdocker\s+(run|build|exec|rm)\b", "Docker operations"),
    (r"\bpython3?\s+-m\s+venv\b", "Create a virtual environment"),
    (r"\bvim?\b|\bnano\b|\bemacs\b", "Open an interactive editor"),
    (r">>", "Append-redirect to a file"),
    (r">\s*\S", "Redirect/overwrite a file"),
    (r"\bmv\b", "Move/rename files"),
    (r"\bcp\b", "Copy files"),
    (r"\bmkdir\b", "Create directories"),
    (r"\btouch\b", "Create/Update files"),
    (r"\bexport\b", "Modify environment variables"),
    (r"\bsed\s+-i\b", "In-place file edit (sed -i)"),
    (r"\bapt\s+update\b", "Refresh package lists"),
]


# ── SAFE: read-only, informative ──────────────────────────────────────────────
SAFE_PATTERNS: list[tuple[str, str]] = [
    (r"\bls\b", "List directory contents"),
    (r"\bcat\b", "Print file contents"),
    (r"\bhead\b", "Show file head"),
    (r"\btail\b", "Show file tail"),
    (r"\bpwd\b", "Print working directory"),
    (r"\becho\b", "Print text"),
    (r"\bclear\b", "Clear screen"),
    (r"\bgit\s+status\b", "Show repo status"),
    (r"\bgit\s+log\b", "Show commit log"),
    (r"\bgit\s+show\b", "Show an object"),
    (r"\bgit\s+diff\b", "Show changes"),
    (r"\bgit\s+branch\b", "List branches"),
    (r"\bpython3?\s+-m\s+venv", "Create virtualenv (safe)"),
    (r"\bpoetry\s+show\b", "Show poetry info"),
    (r"\bpip\s+list\b", "List installed packages"),
    (r"\bnpm\s+list\b", "List installed packages"),
    (r"\bwhich\b", "Locate a binary"),
    (r"\bdate\b", "Show date"),
    (r"\bcal\b", "Show calendar"),
    (r"\bhostname\b", "Show hostname"),
    (r"\bwhoami\b", "Show current user"),
    (r"\bid\b", "Show user/group ids"),
    (r"\buname\b", "Show system info"),
    (r"\bwc\b", "Count lines/words"),
    (r"\bgrep\b", "Search text"),
    (r"\bless\b", "Paginate output"),
    (r"\bmore\b", "Paginate output"),
    (r"\btree\b", "Show directory tree"),
    (r"\bfile\b", "Identify file type"),
    (r"\bdu\b", "Show disk usage"),
    (r"\bdf\b", "Show free disk space"),
    (r"\benv\b", "Show environment"),
    (r"\bprintenv\b", "Show environment"),
]


def _classify_single(cmd: str) -> RiskLevel:
    """Classify a single (whitespace-normalised) command."""
    for pattern, _ in HIGH_RISK_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return RiskLevel.HIGH
    for pattern, _ in MEDIUM_RISK_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return RiskLevel.MEDIUM
    for pattern, _ in SAFE_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return RiskLevel.SAFE
    # Unknown command → treat as MEDIUM so the user is asked before it runs.
    return RiskLevel.MEDIUM


def classify_command(command: str) -> RiskLevel:
    """Classify *command*, handling chained commands correctly.

    Chains joined by ``;``, ``&&`` or ``||`` take the *highest* risk among the
    parts. A bare path or an empty command is not, by itself, dangerous.
    """
    if not command or not command.strip():
        return RiskLevel.SAFE

    normalized = " ".join(command.split())

    # Split on shell chaining operators so each segment is classified
    # independently and the chain takes the highest risk among them.
    parts = re.split(r"\s*;\s*|\s*&&\s*|\s*\|\|\s*", normalized)
    levels = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        levels.append(_classify_single(part))

    if not levels:
        return RiskLevel.MEDIUM

    if RiskLevel.HIGH in levels:
        return RiskLevel.HIGH
    if RiskLevel.MEDIUM in levels:
        return RiskLevel.MEDIUM
    return RiskLevel.SAFE


def get_risk_explanation(command: str) -> str:
    """Return a human-readable reason for the classification."""
    normalized = " ".join(command.split())
    for pattern, reason in HIGH_RISK_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            return reason
    for pattern, reason in MEDIUM_RISK_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            return reason
    for pattern, reason in SAFE_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            return reason
    return "Unrecognised command — requires manual approval"


def validate_command_composition(command: str) -> Tuple[bool, str]:
    """Reject obviously malicious compound commands."""
    if not command.strip():
        return False, "Empty command"

    dangerous_chains = [
        r"\brm\b.*&&\s*\brm\b",
        r"\bdd\b.*&&\s*\brm\b",
        r"\bmkfs\b.*&&\s*\bmount\b",
        r":\(\)\s*\{.*\};:",
    ]
    for pattern in dangerous_chains:
        if re.search(pattern, command, re.IGNORECASE):
            return False, "Dangerous command chain detected"

    return True, ""


def is_read_only_command(command: str) -> bool:
    """True if the command only reads state (useful for auto-approval hints)."""
    return classify_command(command) == RiskLevel.SAFE
