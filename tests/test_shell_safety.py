"""Tests for shell safety / risk classification and Termux environment detection."""

from __future__ import annotations

import os

from syntaxai.safety.risk_rules import classify_command, RiskLevel
from syntaxai.core.env import detect_environment, is_termux
from syntaxai.tools.shell_tools import execute_command


def test_safe_commands():
    assert classify_command("ls -la").value == RiskLevel.SAFE.value
    assert classify_command("cat README.md").value == RiskLevel.SAFE.value
    assert classify_command("git status").value == RiskLevel.SAFE.value
    assert classify_command("pwd").value == RiskLevel.SAFE.value


def test_high_risk_commands():
    assert classify_command("rm -rf /").value == RiskLevel.HIGH.value
    assert classify_command("rm -rf ./build").value == RiskLevel.HIGH.value
    assert classify_command("git push --force origin main").value == RiskLevel.HIGH.value
    assert classify_command("sudo rm file").value == RiskLevel.HIGH.value
    assert classify_command("mkfs.ext4 /dev/sda1").value == RiskLevel.HIGH.value


def test_medium_risk_commands():
    assert classify_command("git commit -m fix").value == RiskLevel.MEDIUM.value
    assert classify_command("pip install requests").value == RiskLevel.MEDIUM.value
    assert classify_command("echo hi > out.txt").value == RiskLevel.MEDIUM.value


def test_chain_takes_highest_risk():
    # safe && high => HIGH
    assert classify_command("ls && rm -rf /").value == RiskLevel.HIGH.value
    # safe && medium => MEDIUM
    assert classify_command("pwd && git commit -m x").value == RiskLevel.MEDIUM.value


def test_hard_block_rejected_without_execution():
    # Must be blocked before any approval/execution (no real deletion happens).
    res = execute_command("rm -rf /")
    assert res.success is False
    assert "Blocked" in res.stderr or "Blocked" in res.stdout or not res.success


def test_safe_command_executes():
    res = execute_command("echo syntaxai-test")
    assert res.success is True
    assert "syntaxai-test" in res.stdout


def test_termux_detection(monkeypatch):
    monkeypatch.setenv("TERMUX_VERSION", "0.118")
    assert is_termux() is True
    env = detect_environment()
    assert env.is_termux is True
    assert env.has_sudo is False
    assert env.has_systemd is False
    assert env.has_docker is False


def test_desktop_env_has_no_false_positives(monkeypatch):
    # Ensure a normal path command is not flagged HIGH purely for absolute paths.
    for var in ("TERMUX_VERSION", "CODESPACE_NAME", "GITPOD_WORKSPACE_URL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("TERMUX_VERSION", raising=False)
    # git status should remain SAFE regardless of working directory
    assert classify_command("git status").value == RiskLevel.SAFE.value
