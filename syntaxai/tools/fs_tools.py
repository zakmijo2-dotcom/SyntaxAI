"""File system tools for SyntaxAI."""

import os
import difflib
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


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


SENSITIVE_PATTERNS = [
    ".env",
    ".env.local",
    ".env.*",
    "*.key",
    "*.pem",
    "*.p12",
    "*.crt",
    "*.cert",
    ".git/",
    ".github/",
    "*.secret",
]


def is_sensitive_path(path: str) -> bool:
    path_obj = Path(path)
    for pattern in SENSITIVE_PATTERNS:
        if pattern.startswith("."):
            if path_obj.name == pattern[1:] or path_obj.name.startswith(pattern[:-1]):
                return True
            if pattern.endswith("/*"):
                if path_obj.parent.name == pattern[:-2]:
                    return True
        elif pattern.endswith("*"):
            if path_obj.suffix == pattern[:-1]:
                return True
        else:
            if pattern in path:
                return True
    return False


def read_file(path: str) -> ReadResult:
    try:
        path_obj = Path(path).resolve()
        
        if is_sensitive_path(str(path_obj)):
            return ReadResult(
                success=False,
                content="",
                error=f"Access denied: '{path}' is a sensitive file. Reading requires explicit permission."
            )
        
        if not path_obj.exists():
            return ReadResult(success=False, content="", error=f"File not found: {path}")
        
        if path_obj.is_dir():
            return ReadResult(success=False, content="", error=f"Path is a directory: {path}")

        with open(path_obj, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        
        return ReadResult(success=True, content=content)

    except PermissionError:
        return ReadResult(success=False, content="", error=f"Permission denied: {path}")
    except Exception as e:
        return ReadResult(success=False, content="", error=str(e))


def write_file(path: str, content: str) -> WriteResult:
    try:
        path_obj = Path(path).resolve()
        
        if is_sensitive_path(str(path_obj)):
            return WriteResult(
                success=False,
                error=f"Access denied: '{path}' is a sensitive file. Writing requires explicit permission."
            )

        path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path_obj, "w", encoding="utf-8") as f:
            f.write(content)
        
        return WriteResult(success=True)

    except PermissionError:
        return WriteResult(success=False, error=f"Permission denied: {path}")
    except Exception as e:
        return WriteResult(success=False, error=str(e))


def edit_file(path: str, old: str, new: str) -> EditResult:
    try:
        result = read_file(path)
        if not result.success:
            return EditResult(success=False, error=result.error)

        content = result.content
        
        if old not in content:
            matches = list(difflib.ndiff(content.splitlines(keepends=True), old.splitlines(keepends=True)))
            similar_lines = []
            for i, (a, b) in enumerate(zip(content.splitlines(keepends=True), old.splitlines(keepends=True))):
                if a != b:
                    similar_lines.append((i+1, a.strip(), b.strip()))
            
            return EditResult(
                success=False,
                error=f"Pattern not found in file. Similar lines: {similar_lines[:3]}"
            )

        new_content = content.replace(old, new, 1)
        
        return write_file(path, new_content)

    except Exception as e:
        return EditResult(success=False, error=str(e))


def list_tree(path: str = ".", depth: int = 3) -> str:
    try:
        path_obj = Path(path).resolve()
        
        if depth < 0:
            depth = 0
        if depth > 10:
            depth = 10

        ignored_dirs = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", ".idea", ".vscode"}
        
        lines = []
        lines.append(f"{path}/\n")
        
        for root, dirs, files in os.walk(path_obj):
            rel_root = Path(root).relative_to(path_obj) if Path(root) != path_obj else Path(".")
            depth_level = len(rel_root.parts) if rel_root != Path(".") else 0
            
            if depth_level >= depth:
                dirs[:] = []
                continue
            
            dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
            
            indent = "    " * depth_level
            for d in sorted(dirs):
                lines.append(f"{indent}├── {d}/")
            
            for f in sorted(files):
                lines.append(f"{indent}├── {f}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error listing tree: {str(e)}"


def list_sensitive_files(path: str = ".") -> str:
    try:
        path_obj = Path(path).resolve()
        sensitive = []
        
        for pattern in SENSITIVE_PATTERNS:
            for match in path_obj.glob(pattern):
                sensitive.append(str(match))
        
        return "\n".join(sensitive) if sensitive else "No sensitive files found."

    except Exception as e:
        return f"Error listing sensitive files: {str(e)}"


def file_exists(path: str) -> bool:
    return Path(path).exists()


def get_file_size(path: str) -> Optional[int]:
    try:
        return Path(path).stat().st_size
    except Exception:
        return None