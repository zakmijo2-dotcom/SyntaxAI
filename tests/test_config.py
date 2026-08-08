"""Tests for configuration persistence and mobile-aware loading."""

from __future__ import annotations

import textwrap
from pathlib import Path

from syntaxai.core.config import Config, ProviderType, ProviderConfig


def test_default_config_fields():
    cfg = Config()
    # New mobile-aware fields must exist with desktop defaults.
    assert cfg.max_context_tokens == 32000
    assert cfg.max_tool_output_chars == 8000
    assert cfg.max_file_read_chars == 20000
    assert cfg.connect_timeout == 10.0
    assert cfg.read_timeout == 60.0
    assert cfg.max_steps == 20


def test_save_and_load_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TERMUX_VERSION", "")  # ensure not auto-mobile
    cfg_path = tmp_path / "config.yaml"
    monkeypatch.setattr(Config, "get_config_path", classmethod(lambda cls: cfg_path))

    cfg = Config()
    cfg.mobile_mode = True
    cfg.max_steps = 12
    cfg.save()

    loaded = Config.load()
    assert loaded.mobile_mode is True
    assert loaded.max_steps == 12


def test_providers_parsed(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TERMUX_VERSION", "")
    cfg_path = tmp_path / "config.yaml"
    monkeypatch.setattr(Config, "get_config_path", classmethod(lambda cls: cfg_path))
    cfg_path.write_text(textwrap.dedent(
        """\
        default_provider: deepseek
        light_model: deepseek-chat
        heavy_model: deepseek-reasoner
        providers:
          - name: deepseek
            api_key: null
            model: deepseek-chat
            enabled: true
        """
    ))
    cfg = Config.load()
    assert cfg.default_provider == ProviderType.DEEPSEEK
    assert cfg.providers[0].name == ProviderType.DEEPSEEK
