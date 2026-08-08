"""Interactive session and query commands for SyntaxAI."""

from __future__ import annotations

import os
from pathlib import Path


def run_interactive(model: str = None) -> int:
    """Run the interactive REPL session."""
    from syntaxai.pi_adapter import PiSyntaxAgent

    model = model or os.environ.get("SYNTAXAI_MODEL", "anthropic/claude-sonnet-4")

    agent = PiSyntaxAgent(model=model)
    agent.run_interactive()
    return 0


def run_query(query: str, model: str = None, event_sink=None) -> str:
    """Run a single query and return the response."""
    from syntaxai.pi_adapter import PiSyntaxAgent
    from syntaxai.skills import extract_skills_from_project, find_matching_skills, load_skill_full

    model = model or os.environ.get("SYNTAXAI_MODEL", "anthropic/claude-sonnet-4")

    agent = PiSyntaxAgent(model=model, event_sink=event_sink)

    skills = extract_skills_from_project()
    for skill in find_matching_skills(query, skills):
        load_skill_full(skill)

    return agent.run(query)


def inspect_project(path: str = None) -> dict:
    """Inspect the current or specified project."""
    import subprocess

    project_path = Path(path or ".").resolve()

    result = {
        "path": str(project_path),
        "files": [],
        "python_files": [],
        "has_git": False,
        "git_status": None,
    }

    if project_path.exists():
        python_files = list(project_path.rglob("*.py"))
        result["python_files"] = [str(f.relative_to(project_path)) for f in python_files[:50]]

        if len(python_files) > 50:
            result["python_files"].append(f"... and {len(python_files) - 50} more")

        try:
            subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=project_path,
                capture_output=True,
                check=True,
            )
            result["has_git"] = True

            status_result = subprocess.run(
                ["git", "status", "--short"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            result["git_status"] = {
                "staged": [l[3:] for l in status_result.stdout.split("\n") if l.startswith("M ") or l.startswith("A ")],
                "unstaged": [l[3:] for l in status_result.stdout.split("\n") if l.startswith(" M")],
                "untracked": [l[2:] for l in status_result.stdout.split("\n") if l.startswith("??")],
            }
        except Exception:
            pass

    return result
