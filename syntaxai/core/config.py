"""Configuration management for SyntaxAI."""

import os
import yaml
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum


class ProviderType(str, Enum):
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    NEMOTRON = "nemotron"


@dataclass
class ProviderConfig:
    name: ProviderType
    api_key: Optional[str] = None
    model: str = ""
    enabled: bool = True


@dataclass
class Config:
    default_provider: ProviderType = ProviderType.GEMINI
    light_model: str = "gemini-1.5-flash"
    heavy_model: str = "gemini-1.5-pro"
    providers: list[ProviderConfig] = field(default_factory=list)

    # ── Context / token budget ───────────────────────────────────────────────
    # Kept for backwards compatibility (older config files / code).
    max_context_length: int = 16000
    # New, explicit token budget used for trimming (see context.py).
    max_context_tokens: int = 32000
    # Characters per token used for cheap estimation (4 ≈ GPT-style).
    token_estimate_chars: int = 4

    # ── Tool / file output limits (prevents huge payloads from blowing context)
    max_tool_output_chars: int = 8000
    max_file_read_chars: int = 20000

    # ── Network / resilience ─────────────────────────────────────────────────
    connect_timeout: float = 10.0
    read_timeout: float = 60.0
    max_retries: int = 2

    # ── Agent loop ───────────────────────────────────────────────────────────
    max_steps: int = 20

    # ── Web server ───────────────────────────────────────────────────────────
    max_concurrent_tasks: int = 4

    # ── Mobile / Termux optimisation ─────────────────────────────────────────
    mobile_mode: bool = False

    # ── Behaviour flags ──────────────────────────────────────────────────────
    auto_approve_safe_commands: bool = True
    log_commands: bool = True
    skill_triggers: dict[str, str] = field(default_factory=dict)

    # Mobile-optimised profile applied automatically on detected Termux devices
    # or when `mobile_mode: true` is set in config.yaml.
    MOBILE_DEFAULTS: dict = field(default_factory=lambda: {
        "max_context_tokens": 12000,
        "max_tool_output_chars": 3000,
        "max_file_read_chars": 8000,
        "connect_timeout": 15.0,
        "read_timeout": 90.0,
        "max_retries": 1,
        "max_steps": 12,
        "max_concurrent_tasks": 1,
        "token_estimate_chars": 4,
    })

    def apply_mobile_profile(self) -> None:
        """Override budget-heavy settings with mobile-optimised values."""
        for key, value in self.MOBILE_DEFAULTS.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.mobile_mode = True

    @classmethod
    def get_config_path(cls) -> Path:
        return Path.home() / ".syntaxai" / "config.yaml"

    @classmethod
    def get_log_path(cls) -> Path:
        return Path.home() / ".syntaxai" / "logs"

    @classmethod
    def get_api_keys_path(cls) -> Path:
        return Path.home() / ".syntaxai" / ".api_keys"

    def save(self) -> None:
        config_dir = self.get_config_path().parent
        config_dir.mkdir(parents=True, exist_ok=True)
        
        data = {
            "default_provider": self.default_provider.value,
            "light_model": self.light_model,
            "heavy_model": self.heavy_model,
            "max_context_length": self.max_context_length,
            "max_context_tokens": self.max_context_tokens,
            "token_estimate_chars": self.token_estimate_chars,
            "max_tool_output_chars": self.max_tool_output_chars,
            "max_file_read_chars": self.max_file_read_chars,
            "connect_timeout": self.connect_timeout,
            "read_timeout": self.read_timeout,
            "max_retries": self.max_retries,
            "max_steps": self.max_steps,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "mobile_mode": self.mobile_mode,
            "auto_approve_safe_commands": self.auto_approve_safe_commands,
            "log_commands": self.log_commands,
            "providers": [
                {
                    "name": p.name.value,
                    "api_key": p.api_key,
                    "model": p.model,
                    "enabled": p.enabled
                }
                for p in self.providers
            ]
        }
        
        with open(self.get_config_path(), "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    @classmethod
    def load(cls) -> "Config":
        config_path = cls.get_config_path()
        
        if not config_path.exists():
            return cls._default_config()
        
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        
        providers = []
        for p_data in data.get("providers", []):
            providers.append(ProviderConfig(
                name=ProviderType(p_data["name"]),
                api_key=p_data.get("api_key"),
                model=p_data.get("model", ""),
                enabled=p_data.get("enabled", True)
            ))
        
        default_provider = ProviderType(data.get("default_provider", "gemini"))

        mobile_mode = data.get("mobile_mode", False)

        cfg = cls(
            default_provider=default_provider,
            light_model=data.get("light_model", "gemini-1.5-flash"),
            heavy_model=data.get("heavy_model", "gemini-1.5-pro"),
            providers=providers,
            max_context_length=data.get("max_context_length", 16000),
            max_context_tokens=data.get("max_context_tokens", 32000),
            token_estimate_chars=data.get("token_estimate_chars", 4),
            max_tool_output_chars=data.get("max_tool_output_chars", 8000),
            max_file_read_chars=data.get("max_file_read_chars", 20000),
            connect_timeout=float(data.get("connect_timeout", 10.0)),
            read_timeout=float(data.get("read_timeout", 60.0)),
            max_retries=data.get("max_retries", 2),
            max_steps=data.get("max_steps", 20),
            max_concurrent_tasks=data.get("max_concurrent_tasks", 4),
            mobile_mode=mobile_mode,
            auto_approve_safe_commands=data.get("auto_approve_safe_commands", True),
            log_commands=data.get("log_commands", True),
        )

        # Auto-apply mobile profile when running on Termux (unless explicitly off).
        if mobile_mode or _running_on_termux():
            cfg.apply_mobile_profile()

        return cfg

    @classmethod
    def _default_config(cls) -> "Config":
        config_dir = cls.get_config_path().parent
        config_dir.mkdir(parents=True, exist_ok=True)
        cfg = cls(
            default_provider=ProviderType.GEMINI,
            light_model="gemini-1.5-flash",
            heavy_model="gemini-1.5-pro",
            providers=[
                ProviderConfig(name=ProviderType.GEMINI, model="gemini-1.5-flash"),
                ProviderConfig(name=ProviderType.DEEPSEEK, model="deepseek-chat"),
                ProviderConfig(name=ProviderType.NEMOTRON, model="nemotron-mini")
            ],
            auto_approve_safe_commands=True,
            log_commands=True,
        )

        if _running_on_termux():
            cfg.apply_mobile_profile()

        return cfg

    def get_api_key(self, provider: ProviderType) -> Optional[str]:
        api_keys_path = self.get_api_keys_path()

        if api_keys_path.exists():
            with open(api_keys_path) as f:
                keys = yaml.safe_load(f) or {}
                return keys.get(provider.value)

        env_var = f"{provider.value.upper()}_API_KEY"
        return os.environ.get(env_var)

    def get_active_provider(self) -> Optional[ProviderConfig]:
        for p in self.providers:
            if p.name == self.default_provider and p.enabled:
                key = p.api_key or self.get_api_key(p.name)
                if key:
                    return ProviderConfig(
                        name=p.name,
                        api_key=key,
                        model=p.model,
                        enabled=p.enabled
                    )
        return None


def _running_on_termux() -> bool:
    """Detect Termux cheaply via env vars (no heavy imports)."""
    return "TERMUX_VERSION" in os.environ