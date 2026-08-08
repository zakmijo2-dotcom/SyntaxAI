"""Environment detection for SyntaxAI (Termux / Linux / macOS / WSL / CI).

A single source of truth so the agent, CLI and tools all agree on what kind of
machine we are running on. Cheap: only reads environment variables and runs a
couple of lightweight checks, with no heavy imports.
"""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class EnvironmentInfo:
    name: str                 # 'android_termux' | 'linux' | 'macos' | 'wsl' | 'codespaces' | 'gitpod' | 'local'
    is_mobile: bool
    is_termux: bool
    has_sudo: bool
    has_systemd: bool
    has_docker: bool
    shell: str
    uname: str

    def capability_note(self) -> str:
        """A short sentence the agent can inject into its system prompt."""
        if self.is_termux:
            return (
                "You are running inside Termux on Android. There is NO sudo, "
                "NO systemd, and NO Docker available. Use 'pkg' for packages "
                "and 'termux-' helper commands. Prefer lightweight commands."
            )
        if self.name == "wsl":
            return "You are running inside WSL on Windows."
        if self.name in ("linux", "macos"):
            return "You are running on a desktop-class OS with full tooling."
        return "You are running in an unknown environment."


def detect_environment() -> EnvironmentInfo:
    termux = "TERMUX_VERSION" in os.environ
    if termux:
        return EnvironmentInfo(
            name="android_termux",
            is_mobile=True,
            is_termux=True,
            has_sudo=False,
            has_systemd=False,
            has_docker=False,
            shell=os.environ.get("SHELL", "/data/data/com.termux/files/usr/bin/bash"),
            uname=platform.platform(),
        )

    if os.environ.get("CODESPACE_NAME"):
        return EnvironmentInfo(
            name="codespaces",
            is_mobile=False,
            is_termux=False,
            has_sudo=True,
            has_systemd=True,
            has_docker=True,
            shell=os.environ.get("SHELL", "/bin/bash"),
            uname=platform.platform(),
        )

    if os.environ.get("GITPOD_WORKSPACE_URL"):
        return EnvironmentInfo(
            name="gitpod",
            is_mobile=False,
            is_termux=False,
            has_sudo=True,
            has_systemd=True,
            has_docker=True,
            shell=os.environ.get("SHELL", "/bin/bash"),
            uname=platform.platform(),
        )

    system = platform.system().lower()
    if system == "linux":
        # WSL detection
        release = platform.release().lower()
        if "microsoft" in release or "wsl" in release:
            return EnvironmentInfo(
                name="wsl",
                is_mobile=False,
                is_termux=False,
                has_sudo=True,
                has_systemd=True,
                has_docker=True,
                shell=os.environ.get("SHELL", "/bin/bash"),
                uname=platform.platform(),
            )
        return EnvironmentInfo(
            name="linux",
            is_mobile=False,
            is_termux=False,
            has_sudo=True,
            has_systemd=True,
            has_docker=_command_exists("docker"),
            shell=os.environ.get("SHELL", "/bin/bash"),
            uname=platform.platform(),
        )

    if system == "darwin":
        return EnvironmentInfo(
            name="macos",
            is_mobile=False,
            is_termux=False,
            has_sudo=True,
            has_systemd=False,
            has_docker=_command_exists("docker"),
            shell=os.environ.get("SHELL", "/bin/zsh"),
            uname=platform.platform(),
        )

    return EnvironmentInfo(
        name="local",
        is_mobile=False,
        is_termux=False,
        has_sudo=False,
        has_systemd=False,
        has_docker=False,
        shell=os.environ.get("SHELL", sys.executable),
        uname=platform.platform(),
    )


def _command_exists(name: str) -> bool:
    from shutil import which

    return which(name) is not None


def is_termux() -> bool:
    return "TERMUX_VERSION" in os.environ


def is_mobile() -> bool:
    return is_termux()
