"""File-system tools for SyntaxAI — hardened path validation."""

from __future__ import annotations

import fnmatch
import logging
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ── sensitive-file detection ───────────────────────────────────────────────────
# Patterns matched against the *resolved absolute path* (not just the basename).
_SENSITIVE_FILENAME_PATTERNS: tuple[str, ...] = (
    ".env", ".env.*",
    "*.key", "*.pem", "*.p12", "*.pfx", "*.crt", "*.cer", "*.cert",
    "*.secret", "*.secrets",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    "credentials", "credentials.*",
    ".netrc", ".pgpass",
)

_SENSITIVE_DIR_PATTERNS: tuple[str, ...] = (
    ".git", ".ssh", ".aws", ".gcloud", ".kube",
)


def is_sensitive_path(path: str) -> bool:
    """Return *True* if *path* refers to a file that should not be
    read/written without explicit permission.

    Resolves symlinks before checking so that ``secret.env ->
    .env`` is also caught.
    """
    try:
        resolved = Path(path).resolve()
    except OSError:
        resolved = Path(path)

    name = resolved.name

    # Check filename patterns
    for pat in _SENSITIVE_FILENAME_PATTERNS:
        if fnmatch.fnmatch(name, pat):
            return True
        if fnmatch.fnmatch(name.lower(), pat.lower()):
            return True

    # Check every ancestor component (catches files inside .git/, .ssh/, …)
    for part in resolved.parts:
        for dir_pat in _SENSITIVE_DIR_PATTERNS:
            if fnmatch.fnmatch(part, dir_pat):
                return True

    return False


def _project_root() -> Optional[Path]:
    """Walk up from cwd to find the nearest project root."""
    markers = {
        ".git", "pyproject.toml", "package.json",
        "Cargo.toml", "go.mod", "pom.xml",
    }
    current = Path.cwd().resolve()
    for candidate in [current, *current.parents]:
        if any((candidate / m).exists() for m in markers):
            return candidate
    return None


def _is_outside_project(path: Path) -> bool:
    """Return *True* if *path* is outside the current project root."""
    root = _project_root()
    if root is None:
        return False  # cannot determine root → allow
    try:
        path.relative_to(root)
        return False
    except ValueError:
        return True


# ── result types ──────────────────────────────────────────────────────────────
@dataclass
class ReadResult:
    success: bool
    content: str
    error: str = ""


@dataclass
class WriteResult:
    success: bool
    error: str = ""


@dataclass
class EditResult:
    success: bool
    error: str = ""


# ── public API ─────────────────────────────────────────────────────────────────
def read_file(path: str) -> ReadResult:
    """Read *path* and return its contents."""
    try:
        p = Path(path).resolve()
    except OSError as exc:
        return ReadResult(False, "", f"Invalid path: {exc}")

    if is_sensitive_path(str(p)):
        return ReadResult(
            False, "",
            f"Access denied: '{path}' is a sensitive file "
            "(pass explicit permission to override).",
        )

    if not p.exists():
        return ReadResult(False, "", f"File not found: {path}")
    if p.is_dir():
        return ReadResult(False, "", f"Path is a directory: {path}")

    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        return ReadResult(True, content)
    except PermissionError:
        return ReadResult(False, "", f"Permission denied: {path}")
    except Exception as exc:
        return ReadResult(False, "", str(exc))


def write_file(path: str, content: str) -> WriteResult:
    """Write *content* to *path*, creating directories as needed."""
    try:
        p = Path(path).resolve()
    except OSError as exc:
        return WriteResult(False, f"Invalid path: {exc}")

    if is_sensitive_path(str(p)):
        return WriteResult(
            False,
            f"Access denied: '{path}' is a sensitive file.",
        )

    if _is_outside_project(p):
        return WriteResult(
            False,
            f"Writing outside the project root is not allowed: {p}",
        )

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return WriteResult(True)
    except PermissionError:
        return WriteResult(False, f"Permission denied: {path}")
    except Exception as exc:
        return WriteResult(False, str(exc))


def edit_file(path: str, old: str, new: str) -> EditResult:
    """Replace the first occurrence of *old* in *path* with *new*."""
    result = read_file(path)
    if not result.success:
        return EditResult(False, result.error)

    if old not in result.content:
        # Provide a helpful diff hint
        old_lines = old.splitlines()
        file_lines = result.content.splitlines()
        hint_lines: list[str] = []
        for ol in old_lines[:3]:
            close = [
                fl for fl in file_lines
                if ol.strip() and ol.strip() in fl
            ]
            if close:
                hint_lines.append(close[0].strip())
        hint = f" (similar lines: {hint_lines})" if hint_lines else ""
        return EditResult(
            False,
            f"Pattern not found in '{path}'{hint}. "
            "Check for whitespace differences or copy the exact text.",
        )

    new_content = result.content.replace(old, new, 1)
    wr = write_file(path, new_content)
    return EditResult(wr.success, wr.error)


def list_tree(path: str = ".", depth: int = 3) -> str:
    """Return a textual directory tree rooted at *path*."""
    depth = max(0, min(depth, 10))
    try:
        root = Path(path).resolve()
    except OSError as exc:
        return f"Error: {exc}"

    if not root.is_dir():
        return f"Not a directory: {path}"

    _SKIP = frozenset({
        ".git", "__pycache__", ".pytest_cache",
        ".venv", "venv", "node_modules",
        ".idea", ".vscode", "dist", "build", ".next",
    })

    lines: list[str] = [f"{root}/"]

    def _walk(directory: Path, current_depth: int, prefix: str) -> None:
        if current_depth >= depth:
            return
        entries = sorted(directory.iterdir(), key=lambda e: (e.is_file(), e.name))
        visible = [e for e in entries if e.name not in _SKIP and not e.name.startswith(".")]
        for i, entry in enumerate(visible):
            is_last = i == len(visible) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
            if entry.is_dir():
                extension = "    " if is_last else "│   "
                _walk(entry, current_depth + 1, prefix + extension)

    _walk(root, 0, "")
    return "\n".join(lines)


def list_sensitive_files(path: str = ".") -> str:
    """Return a list of detected sensitive files under *path*."""
    try:
        root = Path(path).resolve()
    except OSError as exc:
        return f"Error: {exc}"

    found: list[str] = []
    for p in root.rglob("*"):
        if p.is_file() and is_sensitive_path(str(p)):
            try:
                found.append(str(p.relative_to(root)))
            except ValueError:
                found.append(str(p))

    return "\n".join(sorted(found)) if found else "No sensitive files found."


def file_exists(path: str) -> bool:
    return Path(path).exists()


def get_file_size(path: str) -> Optional[int]:
    try:
        return Path(path).stat().st_size
    except OSError:
        return None
