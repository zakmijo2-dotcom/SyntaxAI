"""Tests for new architecture - pi-adapter and workflows."""

from __future__ import annotations

import os
import pytest
import syntaxai.config
from syntaxai.config import Config, ProviderType


def test_config_defaults():
    cfg = Config()
    assert cfg.default_provider == ProviderType.GEMINI
    assert cfg.max_steps == 20
    assert cfg.max_context_tokens == 32000


def test_provider_types():
    assert ProviderType.GEMINI.value == "gemini"
    assert ProviderType.DEEPSEEK.value == "deepseek"
    assert ProviderType.NEMOTRON.value == "nemotron"


def test_provider_config():
    from syntaxai.config import ProviderConfig
    
    cfg = ProviderConfig(
        name=ProviderType.GEMINI,
        api_key="test-key",
        model="gemini-2.5-flash",
        enabled=True,
    )
    
    assert cfg.name == ProviderType.GEMINI
    assert cfg.api_key == "test-key"
    assert cfg.enabled is True


def test_workflows_available():
    from syntaxai.workflows import get_available_workflows
    
    workflows = get_available_workflows()
    assert "autofix" in workflows
    assert "refactor" in workflows
    assert "review" in workflows
    assert "test" in workflows
    assert "analyze" in workflows


def test_autofix_workflow():
    from syntaxai.workflows import execute_workflow
    
    result = execute_workflow("autofix", "README.md")
    assert "README.md" in result


def test_analyze_workflow():
    from syntaxai.workflows import execute_workflow
    
    result = execute_workflow("analyze", ".")
    assert "Python files" in result

    import re
    count_match = re.search(r"Python files: (\d+)", result)
    assert count_match is not None
    assert int(count_match.group(1)) >= 0


def test_review_workflow():
    from syntaxai.workflows import execute_workflow
    
    result = execute_workflow("review", "pyproject.toml")
    assert "Code Review Report" in result


def test_unknown_workflow():
    from syntaxai.workflows import execute_workflow
    
    result = execute_workflow("unknown", "test")
    assert "Unknown workflow" in result


def test_config_api_key_from_env():
    key = os.environ.get("GOOGLE_API_KEY")
    if key:
        cfg = Config()
        retrieved = cfg.get_api_key(ProviderType.GEMINI)
        assert retrieved == key or retrieved is not None


def test_config_save_load_roundtrip(tmp_path, monkeypatch):
    import yaml
    
    monkeypatch.setenv("TERMUX_VERSION", "")
    
    from syntaxai.config import Config
    cfg_path = tmp_path / "config.yaml"
    
    monkeypatch.setattr(Config, "get_config_path", classmethod(lambda cls: cfg_path))
    
    cfg = Config()
    cfg.default_provider = ProviderType.DEEPSEEK
    cfg.save()
    
    loaded = Config.load()
    assert loaded.default_provider == ProviderType.DEEPSEEK


def test_mobile_profile():
    cfg = Config()
    cfg.apply_mobile_profile()
    
    assert cfg.mobile_mode is True
    assert cfg.max_context_tokens == 12000
    assert cfg.max_steps == 12