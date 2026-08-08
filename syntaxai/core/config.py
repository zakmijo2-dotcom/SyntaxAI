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
    max_context_length: int = 16000
    auto_approve_safe_commands: bool = True
    log_commands: bool = True
    skill_triggers: dict[str, str] = field(default_factory=dict)

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
        
        return cls(
            default_provider=default_provider,
            light_model=data.get("light_model", "gemini-1.5-flash"),
            heavy_model=data.get("heavy_model", "gemini-1.5-pro"),
            providers=providers,
            max_context_length=data.get("max_context_length", 16000),
            auto_approve_safe_commands=data.get("auto_approve_safe_commands", True),
            log_commands=data.get("log_commands", True)
        )

    @classmethod
    def _default_config(cls) -> "Config":
        config_dir = cls.get_config_path().parent
        config_dir.mkdir(parents=True, exist_ok=True)
        
        return cls(
            default_provider=ProviderType.GEMINI,
            light_model="gemini-1.5-flash",
            heavy_model="gemini-1.5-pro",
            providers=[
                ProviderConfig(name=ProviderType.GEMINI, model="gemini-1.5-flash"),
                ProviderConfig(name=ProviderType.DEEPSEEK, model="deepseek-chat"),
                ProviderConfig(name=ProviderType.NEMOTRON, model="nemotron-mini")
            ],
            auto_approve_safe_commands=True,
            log_commands=True
        )

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