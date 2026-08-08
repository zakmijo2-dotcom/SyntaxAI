"""Project inspection commands for SyntaxAI."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProjectInfo:
    path: str
    files: list[str] = field(default_factory=list)
    python_files: list[str] = field(default_factory=list)
    has_git: bool = False
    git_branch: str = ""
    git_status: dict = None
    size_bytes: int = 0
    languages: dict = None


def inspect_path(path: str = None) -> ProjectInfo:
    """Inspect a project path and return information."""
    project_path = Path(path or ".").resolve()

    info = ProjectInfo(path=str(project_path))

    if not project_path.exists():
        return info

    if project_path.is_file():
        project_path = project_path.parent

    _collect_files(project_path, info)
    _detect_git(project_path, info)
    _calculate_size(project_path, info)
    _detect_languages(info)

    return info


def _collect_files(path: Path, info: ProjectInfo) -> None:
    """Collect files from the project."""
    SKIP_DIRS = {
        ".git", "__pycache__", ".pytest_cache", ".venv", "venv",
        "node_modules", ".idea", ".vscode", "dist", "build", ".next",
        "target", "Cargo.lock", "package-lock.json", "yarn.lock",
    }

    all_files = []
    python_files = []

    for item in path.rglob("*"):
        if any(skip in item.parts for skip in SKIP_DIRS):
            continue
        if item.is_file():
            rel = str(item.relative_to(path))
            all_files.append(rel)
            if item.suffix == ".py":
                python_files.append(rel)

    info.files = all_files[:100]
    info.python_files = python_files[:50]


def _detect_git(path: Path, info: ProjectInfo) -> None:
    """Detect git repository and status."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=path,
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0:
            info.has_git = True

            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            info.git_branch = branch_result.stdout.strip()

            status_result = subprocess.run(
                ["git", "status", "--short"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5,
            )

            lines = [l for l in status_result.stdout.strip().split("\n") if l]
            info.git_status = {
                "staged": [l[3:] for l in lines if l.startswith("M ") or l.startswith("A ")],
                "unstaged": [l[3:] for l in lines if l.startswith(" M")],
                "untracked": [l[2:] for l in lines if l.startswith("??")],
            }
    except Exception:
        pass


def _calculate_size(path: Path, info: ProjectInfo) -> None:
    """Calculate total project size."""
    total = 0
    for item in path.rglob("*"):
        if item.is_file() and not any(
            skip in item.parts for skip in [".git", "__pycache__", ".venv", "venv", "node_modules"]
        ):
            try:
                total += item.stat().st_size
            except Exception:
                pass
    info.size_bytes = total


def _detect_languages(info: ProjectInfo) -> None:
    """Detect programming languages in the project."""
    extensions = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",
        ".jsx": "JavaScript",
        ".java": "Java",
        ".go": "Go",
        ".rs": "Rust",
        ".rb": "Ruby",
        ".php": "PHP",
        ".swift": "Swift",
        ".kt": "Kotlin",
        ".scala": "Scala",
        ".cs": "C#",
        ".cpp": "C++",
        ".c": "C",
        ".h": "C/C++ Header",
        ".hxx": "C++ Header",
        ".hpp": "C++ Header",
    }

    lang_counts = {}
    for f in info.python_files:
        ext = Path(f).suffix.lower()
        if ext in extensions:
            lang = extensions[ext]
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

    info.languages = lang_counts
