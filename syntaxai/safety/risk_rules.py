"""Command risk classification for SyntaxAI."""

from __future__ import annotations

import re

from syntaxai.safety.approval import RiskLevel


def classify_command(command: str) -> RiskLevel:
    """Classify a command by risk level for approval decisions."""
    command_lower = command.lower().strip()

    safe_patterns = [
        r"^ls\b",
        r"^pwd\b",
        r"^echo\b",
        r"^cat\b",
        r"^head\b",
        r"^tail\b",
        r"^grep\b",
        r"^git\s+status\b",
        r"^git\s+diff\b",
        r"^git\s+log\b",
        r"^git\s+show\b",
        r"^which\b",
        r"^where\b",
        r"^env\b",
        r"^printenv\b",
        r"^python\b.*--version\b",
        r"^pip\b.*list\b",
        r"^pip\b.*show\b",
        r"^python\b.*-c\b.*print\b",
    ]

    for pattern in safe_patterns:
        if re.search(pattern, command_lower):
            return RiskLevel.SAFE

    safe_medium_patterns = [
        r"^pip\b.*install\b",
        r"^pip\b.*uninstall\b",
        r"^python\b.*-m\s+pip\b",
        r"^git\s+commit\b",
        r"^git\s+push\b",
        r"^git\s+pull\b",
        r"^git\s+fetch\b",
        r"^git\s+merg\b",
        r"^git\s+reb\b",
        r"^git\s+checkout\b.*-b\b",
    ]

    for pattern in safe_medium_patterns:
        if re.search(pattern, command_lower):
            return RiskLevel.MEDIUM

    safe_high_patterns = [
        r"\brm\b.*-rf\b.*\b/\b",
        r"\brm\b.*-r\b.*-\s*f\b.*\b/\b",
        r"\bdd\b.*if=.*/dev/",
        r"\bmkfs\b",
        r"\bchmod\b.*-R\s+0",
        r"\bgit\s+push\b.*--force\b",
        r"\bgit\s+push\b.*--force-with-lease\b",
    ]

    for pattern in safe_high_patterns:
        if re.search(pattern, command_lower):
            return RiskLevel.HIGH

    return RiskLevel.SAFE


def is_safe_path(path: str) -> bool:
    """Check if a path is safe to access."""
    sensitive_patterns = [
        r".*\.env$",
        r".*\.env\..*",
        r".*\.key$",
        r".*\.pem$",
        r".*\.p12$",
        r".*\.pfx$",
        r".*\.crt$",
        r".*\.cer$",
        r".*\.cert$",
        r".*\.secret$",
        r".*\.secrets$",
        r".*id_rsa$",
        r".*id_dsa$",
        r".*id_ecdsa$",
        r".*id_ed25519$",
        r".*credentials$",
        r".*credentials\..*",
        r".*\.netrc$",
        r".*\.pgpass$",
        r".*/\.git/.*",
        r".*/\.ssh/.*",
        r".*/\.aws/.*",
        r".*/\.gcloud/.*",
        r".*/\.kube/.*",
    ]

    for pattern in sensitive_patterns:
        if re.match(pattern, path):
            return False
    return True
