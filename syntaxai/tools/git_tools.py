"""Git integration tools for SyntaxAI."""

import os
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class GitStatus:
    is_repo: bool
    branch: str
    staged: list[str]
    unstaged: list[str]
    untracked: list[str]
    clean: bool


def git_status() -> str:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return f"Git error: {result.stderr.strip()}"

        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
        staged = []
        unstaged = []
        untracked = []
        
        for line in lines:
            if line.startswith("??"):
                untracked.append(line[2:])
            elif "M" in line[:2]:
                unstaged.append(line[3:])
                staged.append(line[3:])
            elif line[0] in ["A", "M"]:
                staged.append(line[2:])
            else:
                unstaged.append(line[3:] if len(line) > 3 else line[2:])
        
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"
        
        status_lines = [f"Branch: {branch}", f"Staged: {len(staged)}", f"Unstaged: {len(unstaged)}", f"Untracked: {len(untracked)}"]
        
        if staged:
            status_lines.append(f"\nStaged files:\n" + "\n".join(f"  {f}" for f in staged[:10]))
        if unstaged:
            status_lines.append(f"\nUnstaged files:\n" + "\n".join(f"  {f}" for f in unstaged[:10]))
        if untracked:
            status_lines.append(f"\nUntracked files:\n" + "\n".join(f"  {f}" for f in untracked[:10]))
        
        return "\n".join(status_lines)

    except FileNotFoundError:
        return "Git not found. Please install git."
    except subprocess.TimeoutExpired:
        return "Git status timed out"
    except Exception as e:
        return f"Git status error: {str(e)}"


def git_diff(simplified: bool = True) -> str:
    try:
        if simplified:
            result = subprocess.run(
                ["git", "diff", "--stat"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                return ""
            return result.stdout.strip()
        else:
            result = subprocess.run(
                ["git", "diff"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                return ""
            return result.stdout.strip()

    except Exception as e:
        return f"Git diff error: {str(e)}"


def git_commit(message: str) -> str:
    try:
        if not message:
            return "Commit message required"

        staged_result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        files = [f for f in staged_result.stdout.strip().split("\n") if f]
        
        if not files:
            return "No staged changes to commit"

        preview_lines = ["Files to be committed:"]
        for f in files[:10]:
            preview_lines.append(f"  {f}")
        if len(files) > 10:
            preview_lines.append(f"  ... and {len(files) - 10} more")

        return "\n".join(preview_lines) + f"\n\nCommit message: {message}"

    except Exception as e:
        return f"Git commit preview error: {str(e)}"


def git_push(remote: str = "origin", branch: str = None) -> str:
    try:
        if branch is None:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5
            )
            branch = result.stdout.strip() if result.returncode == 0 else "main"

        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if status_result.stdout.strip():
            return "Uncommitted changes present. Please commit or stash first."

        diff_result = subprocess.run(
            ["git", "log", "--oneline", "-5", f"{remote}/{branch}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        remote_commits = diff_result.stdout.strip().split("\n") if diff_result.stdout.strip() else []
        remote_commits = [c for c in remote_commits if c]

        info_lines = [
            f"Push preview:",
            f"  Remote: {remote}",
            f"  Branch: {branch}",
            f"  Has {len(remote_commits)} remote commits"
        ]

        if remote_commits:
            info_lines.append("  Remote recent commits:")
            for c in remote_commits[:3]:
                info_lines.append(f"    {c}")

        return "\n".join(info_lines)

    except Exception as e:
        return f"Git push preview error: {str(e)}"


def get_current_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def is_git_repo() -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def get_remote_url() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def create_branch(branch_name: str) -> str:
    try:
        result = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        return f"Created and switched to branch: {branch_name}" if result.returncode == 0 else result.stderr.strip()
    except Exception as e:
        return f"Branch creation error: {str(e)}"


def list_branches() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "branch", "-a"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        branches = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line.startswith("* "):
                line = line[2:]
            if line and not line.startswith("remotes/"):
                branches.append(line)
            elif "remotes/" in line:
                parts = line.split("remotes/")
                if len(parts) > 1:
                    branches.append(parts[1])
        
        return branches
    except Exception:
        return []