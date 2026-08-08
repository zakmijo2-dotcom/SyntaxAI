"""Code review commands for SyntaxAI."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ReviewIssue:
    severity: str
    file: str
    line: int
    message: str
    suggestion: str = ""


def review_file(path: str, include_suggestions: bool = True) -> list[ReviewIssue]:
    """Review a single file for potential issues."""
    issues = []
    file_path = Path(path)

    if not file_path.exists():
        return issues

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return issues

    lines = content.split("\n")

    for i, line in enumerate(lines, 1):
        # TODO: fix
        if re.search(r"#\s*TODO\s*:", line, re.IGNORECASE):
            issues.append(ReviewIssue(
                severity="low",
                file=path,
                line=i,
                message="TODO comment found",
                suggestion="Consider addressing this TODO or convert to an issue",
            ))

        # FIXME: fix
        if re.search(r"#\s*FIXME\s*:", line, re.IGNORECASE):
            issues.append(ReviewIssue(
                severity="medium",
                file=path,
                line=i,
                message="FIXME comment found",
                suggestion="Address this issue before merging",
            ))

        # Print statement (potential debug leak)
        if "print(" in line and "#" not in line.split("print")[0]:
            issues.append(ReviewIssue(
                severity="low",
                file=path,
                line=i,
                message="Print statement found",
                suggestion="Consider using logging instead",
            ))

        # Hardcoded secrets detection
        if re.search(r'password\s*=\s*["\']|api_key\s*=\s*["\']|secret\s*=\s*["\']', line, re.IGNORECASE):
            issues.append(ReviewIssue(
                severity="high",
                file=path,
                line=i,
                message="Potential hardcoded secret",
                suggestion="Use environment variables or secret management",
            ))

    return issues


def review_code(code: str, language: str = "python") -> str:
    """Review code string and return issues."""
    issues = []
    lines = code.split("\n")

    for i, line in enumerate(lines, 1):
        # Unused imports (basic check)
        if language == "python" and re.match(r"^\s*import\s+\w+", line):
            import_match = re.match(r"^\s*import\s+(\w+)", line)
            if import_match:
                imp = import_match.group(1)
                if imp not in code[:code.find(line)].split("\n")[0] + code[code.find(line):]:
                    pass  # Could do more sophisticated check

        # Dead code / unused variables
        if language == "python" and re.match(r"^\s*_\s*=", line):
            issues.append(f"Line {i}: Unused variable (assigned to _)")

    if issues:
        return "Review issues found:\n" + "\n".join(f"- {i}" for i in issues)
    return "No issues found"
