"""Tool system for SyntaxAI - wraps Pi Agent CLI capabilities."""

from __future__ import annotations

import os
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pi_llm import TextContent
from pi_llm_agent import AgentTool, AgentToolResult

from syntaxai.safety.approval import get_approval, log_command
from syntaxai.safety.risk_rules import classify_command, is_safe_path


def truncate_output(text: str, limit: int = 30000) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    keep_head = max(limit // 2, 256)
    keep_tail = limit - keep_head
    head = text[:keep_head]
    tail = text[-keep_tail:]
    omitted = len(text) - keep_head - keep_tail
    return (
        f"{head}\n\n"
        f"... [output truncated: {omitted} chars omitted of {len(text)} total] ...\n\n"
        f"{tail}"
    )


def read_text_truncated(path: Path, max_chars: int = 30000, encoding: str = "utf-8") -> str:
    if path.stat().st_size <= max_chars:
        return path.read_text(encoding=encoding, errors="replace")

    keep_head = max(max_chars // 2, 256)
    keep_tail = max_chars - keep_head

    with open(path, encoding=encoding, errors="replace") as f:
        head = f.read(keep_head)
        f.seek(0, 2)
        file_size = f.tell()
        f.seek(max(0, file_size - keep_tail))
        tail = f.read()

    omitted = path.stat().st_size - len(head) - len(tail)
    return (
        f"{head}\n\n"
        f"... [file truncated: {max(omitted, 0)} bytes omitted of {file_size} total] ...\n\n"
        f"{tail}"
    )


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


def get_project_root() -> Path | None:
    markers = [".git", "pyproject.toml", "package.json", "Cargo.toml", "go.mod", "pom.xml"]
    current = Path.cwd().resolve()
    for candidate in [current, *current.parents]:
        if any((candidate / m).exists() for m in markers):
            return candidate
    return None


def read_file_impl(path: str) -> ReadResult:
    try:
        p = Path(path).resolve()
    except OSError as exc:
        return ReadResult(False, "", f"Invalid path: {exc}")

    if not is_safe_path(str(p)):
        return ReadResult(
            False, "",
            f"Access denied: '{path}' is a sensitive file.",
        )

    if not p.exists():
        return ReadResult(False, "", f"File not found: {path}")
    if p.is_dir():
        return ReadResult(False, "", f"Path is a directory: {path}")

    root = get_project_root()
    if root and not str(p).startswith(str(root)):
        return ReadResult(False, "", f"Access denied: path outside project root: {path}")

    try:
        content = read_text_truncated(p)
        return ReadResult(True, content)
    except PermissionError:
        return ReadResult(False, "", f"Permission denied: {path}")
    except Exception as exc:
        return ReadResult(False, "", str(exc))


def write_file_impl(path: str, content: str) -> WriteResult:
    try:
        p = Path(path).resolve()
    except OSError as exc:
        return WriteResult(False, f"Invalid path: {exc}")

    if not is_safe_path(str(p)):
        return WriteResult(False, f"Access denied: '{path}' is a sensitive file.")

    root = get_project_root()
    if root and not str(p).startswith(str(root)):
        return WriteResult(False, f"Writing outside project root is not allowed: {p}")

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return WriteResult(True)
    except PermissionError:
        return WriteResult(False, f"Permission denied: {path}")
    except Exception as exc:
        return WriteResult(False, str(exc))


def edit_file_impl(path: str, old: str, new: str) -> EditResult:
    result = read_file_impl(path)
    if not result.success:
        return EditResult(False, result.error)

    if old not in result.content:
        old_lines = old.splitlines()
        file_lines = result.content.splitlines()
        hint_lines = []
        for ol in old_lines[:3]:
            close = [fl for fl in file_lines if ol.strip() and ol.strip() in fl]
            if close:
                hint_lines.append(close[0].strip())
        hint = f" (similar lines: {hint_lines})" if hint_lines else ""
        return EditResult(
            False,
            f"Pattern not found in '{path}'{hint}. Check for whitespace differences.",
        )

    new_content = result.content.replace(old, new, 1)
    wr = write_file_impl(path, new_content)
    return EditResult(wr.success, wr.error)


def list_tree_impl(path: str = ".", depth: int = 3) -> str:
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

    lines = [f"{root}/"]

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
    tree = "\n".join(lines)
    return truncate_output(tree, 20000)


def execute_command_impl(command: str, cwd: str | None = None) -> tuple[bool, str, str]:
    command = command.strip()
    if not command:
        return False, "", "Empty command"

    blocked_patterns = [
        (r"\brm\s+-rf\s+/\s*$", "rm -rf /"),
        (r"\brm\s+-rf\s+/\*\s*$", "rm -rf /*"),
        (r"\brm\s+-rf\s+/[^a-zA-Z0-9]", "rm -rf /<root>"),
        (r":\(\)\s*\{", "fork bomb"),
        (r"\bmkfs\b", "mkfs"),
        (r"\bdd\s+if=\s*/dev/", "dd disk overwrite"),
    ]

    import re
    for pattern, reason in blocked_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return False, "", f"Blocked: {reason}"

    risk = classify_command(command)
    if risk.value == "high":
        approved = get_approval(command, {"command": command, "args": {}}, "high")
        if not approved:
            return False, "", "Cancelled by user (HIGH risk)"
    elif risk.value == "medium":
        approved = get_approval(command, {"command": command, "args": {}}, "medium")
        if not approved:
            return False, "", "Cancelled by user (MEDIUM risk)"
    else:
        approved = True

    working_dir = cwd or str(Path.cwd())
    if not Path(working_dir).is_dir():
        return False, "", f"Directory not found: {working_dir}"

    log_command(command, risk.value, approved, "", "")

    try:
        shell_chars = re.compile(r"[|;&<>$`]")
        use_shell = bool(shell_chars.search(command))

        if use_shell:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=working_dir,
                env=os.environ.copy(),
            )
        else:
            try:
                args = shlex.split(command)
            except ValueError as exc:
                return False, "", f"Command parse error: {exc}"
            proc = subprocess.run(
                args,
                shell=False,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=working_dir,
                env=os.environ.copy(),
            )

        stdout = proc.stdout[:5000] if proc.stdout else ""
        stderr = proc.stderr[:5000] if proc.stderr else ""
        return proc.returncode == 0, stdout, stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except FileNotFoundError as exc:
        return False, "", f"Command not found: {exc}"
    except Exception as exc:
        return False, "", str(exc)


# Tool factory functions that create Pi-compatible AgentTool instances

def create_read_tool() -> AgentTool:
    async def read_execute(tool_call_id: str, params: dict, cancellation=None, on_update=None):
        path = params.get("path", "")
        if not path:
            raise ValueError("Missing required argument: path")
        result = read_file_impl(path)
        if result.success:
            return AgentToolResult(
                content=[TextContent(text=result.content)],
                details={"path": path},
            )
        raise FileNotFoundError(result.error)

    return AgentTool(
        name="read_file",
        label="Read File",
        description="Read the contents of a file on disk.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read"},
            },
            "required": ["path"],
        },
        execute=read_execute,
    )


def create_write_tool() -> AgentTool:
    async def write_execute(tool_call_id: str, params: dict, cancellation=None, on_update=None):
        path = params.get("path", "")
        content = params.get("content", "")
        if not path:
            raise ValueError("Missing required argument: path")
        result = write_file_impl(path, content)
        if result.success:
            return AgentToolResult(
                content=[TextContent(text=f"Written: {path}")],
                details={"path": path},
            )
        raise ValueError(result.error)

    return AgentTool(
        name="write_file",
        label="Write File",
        description="Create or overwrite a file with the given content.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to write"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
        execute=write_execute,
        execution_mode="sequential",
    )


def create_edit_tool() -> AgentTool:
    async def edit_execute(tool_call_id: str, params: dict, cancellation=None, on_update=None):
        path = params.get("path", "")
        old = params.get("old", "")
        new = params.get("new", "")
        if not path:
            raise ValueError("Missing required argument: path")
        result = edit_file_impl(path, old, new)
        if result.success:
            return AgentToolResult(
                content=[TextContent(text=f"Edited: {path}")],
                details={"path": path},
            )
        raise ValueError(result.error)

    return AgentTool(
        name="edit_file",
        label="Edit File",
        description="Replace a specific substring in a file (diff-style editing).",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to edit"},
                "old": {"type": "string", "description": "Exact text to replace"},
                "new": {"type": "string", "description": "Replacement text"},
            },
            "required": ["path", "old", "new"],
        },
        execute=edit_execute,
        execution_mode="sequential",
    )


def create_list_tool() -> AgentTool:
    async def list_execute(tool_call_id: str, params: dict, cancellation=None, on_update=None):
        path = params.get("path", ".")
        depth = int(params.get("depth", 3))
        result = list_tree_impl(path, depth)
        return AgentToolResult(
            content=[TextContent(text=result)],
        )

    return AgentTool(
        name="list_tree",
        label="List Directory Tree",
        description="List the directory tree up to a given depth.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path (default: '.')"},
                "depth": {"type": "integer", "description": "Tree depth, 1-10 (default: 3)"},
            },
        },
        execute=list_execute,
    )


def create_shell_tool(approval_handler: Callable | None = None) -> AgentTool:
    async def shell_execute(tool_call_id: str, params: dict, cancellation=None, on_update=None):
        command = params.get("command", "")
        if not command:
            raise ValueError("Missing required argument: command")

        risk = classify_command(command)
        if risk != RiskLevel.SAFE:
            approved = get_approval("shell", {"command": command}, risk.value)
            if not approved:
                raise PermissionError("Cancelled by user")

        success, stdout, stderr = execute_command_impl(command)
        if success:
            output = truncate_output(stdout + stderr)
            return AgentToolResult(
                content=[TextContent(text=output)],
                details={"command": command, "exit_code": 0},
            )
        raise RuntimeError(truncate_output(stderr))

    return AgentTool(
        name="shell",
        label="Shell Command",
        description="Execute a shell command. Dangerous commands require user approval.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
                "cwd": {"type": "string", "description": "Working directory (optional)"},
            },
            "required": ["command"],
        },
        execute=shell_execute,
        execution_mode="sequential",
    )


def create_git_status_tool() -> AgentTool:
    async def git_status_execute(tool_call_id: str, params: dict, cancellation=None, on_update=None):
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return AgentToolResult(content=[TextContent(text="Not in a git repository")])

            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"

            lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
            staged = [l[3:] for l in lines if l.startswith("M ") or l.startswith("A ")]
            unstaged = [l[3:] for l in lines if l.startswith(" M")]
            untracked = [l[2:] for l in lines if l.startswith("??")]

            output_lines = [f"Branch: {branch}", f"Staged: {len(staged)}", f"Unstaged: {len(unstaged)}", f"Untracked: {len(untracked)}"]
            return AgentToolResult(
                content=[TextContent(text="\n".join(output_lines))],
            )
        except FileNotFoundError:
            raise RuntimeError("Git not found")
        except Exception as e:
            raise RuntimeError(str(e))

    return AgentTool(
        name="git_status",
        label="Git Status",
        description="Return the current git repository status.",
        parameters={"type": "object", "properties": {}, "required": []},
        execute=git_status_execute,
    )


def create_git_diff_tool() -> AgentTool:
    async def git_diff_execute(tool_call_id: str, params: dict, cancellation=None, on_update=None):
        try:
            result = subprocess.run(
                ["git", "diff", "--stat"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return AgentToolResult(
                content=[TextContent(text=result.stdout.strip() or "No changes")],
            )
        except Exception as e:
            raise RuntimeError(str(e))

    return AgentTool(
        name="git_diff",
        label="Git Diff",
        description="Return the current git diff.",
        parameters={"type": "object", "properties": {}, "required": []},
        execute=git_diff_execute,
    )


def create_git_commit_tool() -> AgentTool:
    async def git_commit_execute(tool_call_id: str, params: dict, cancellation=None, on_update=None):
        message = params.get("message", "")
        if not message:
            raise ValueError("Missing required argument: message")

        staged_result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        files = [f for f in staged_result.stdout.strip().split("\n") if f]

        if not files:
            raise RuntimeError("No staged changes to commit")

        preview = ["Files to be committed:"] + [f"  {f}" for f in files[:10]]
        if len(files) > 10:
            preview.append(f"  ... and {len(files) - 10} more")

        return AgentToolResult(
            content=[TextContent(text="\n".join(preview) + f"\n\nCommit: {message}")],
            details={"files": len(files)},
        )

    return AgentTool(
        name="git_commit",
        label="Git Commit",
        description="Stage all changes and create a git commit.",
        parameters={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Commit message"},
            },
            "required": ["message"],
        },
        execute=git_commit_execute,
    )


def create_git_push_tool() -> AgentTool:
    async def git_push_execute(tool_call_id: str, params: dict, cancellation=None, on_update=None):
        import subprocess
        remote = params.get("remote", "origin")
        branch = params.get("branch")

        if not branch:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            branch = result.stdout.strip() if result.returncode == 0 else "main"

        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if status_result.stdout.strip():
            raise RuntimeError("Uncommitted changes present. Please commit or stash first.")

        diff_result = subprocess.run(
            ["git", "log", "--oneline", "-5", f"{remote}/{branch}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        remote_commits = [c for c in diff_result.stdout.strip().split("\n") if c]

        lines = [
            "Push preview:",
            f"  Remote: {remote}",
            f"  Branch: {branch}",
            f"  Has {len(remote_commits)} remote commits",
        ]
        return AgentToolResult(
            content=[TextContent(text="\n".join(lines))],
        )

    return AgentTool(
        name="git_push",
        label="Git Push",
        description="Push committed changes to a remote repository.",
        parameters={
            "type": "object",
            "properties": {
                "remote": {"type": "string", "description": "Remote name (default: origin)"},
                "branch": {"type": "string", "description": "Branch name (default: current)"},
            },
        },
        execute=git_push_execute,
    )


def create_git_tools() -> list[AgentTool]:
    """Create all git-related tools for SyntaxAI."""
    return [
        create_git_status_tool(),
        create_git_diff_tool(),
        create_git_commit_tool(),
        create_git_push_tool(),
    ]
