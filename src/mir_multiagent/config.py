"""Environment-driven configuration with explicit provider validation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

SUPPORTED_PROVIDERS = {"mock", "groq", "openai_compatible"}
AGENT_NAMES = ("answer", "pharmacology", "clinical", "terminology", "mnemonic")


class ConfigurationError(ValueError):
    """Raised when runtime configuration is incomplete or unsupported."""


@dataclass(frozen=True)
class Settings:
    provider: str = "mock"
    default_model: str = "deterministic-demo"
    base_url: str | None = None
    api_key: str | None = None
    agent_models: dict[str, str] = field(default_factory=dict)
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass

        provider = os.getenv("MIR_LLM_PROVIDER", "mock").strip().lower()
        default_model = os.getenv("MIR_LLM_MODEL", "deterministic-demo").strip()
        base_url = os.getenv("MIR_LLM_BASE_URL") or None
        if provider == "groq":
            api_key = os.getenv("GROQ_API_KEY") or None
        else:
            api_key = os.getenv("MIR_LLM_API_KEY") or None

        models = {
            name: os.getenv(f"MIR_{name.upper()}_MODEL", "").strip() or default_model
            for name in AGENT_NAMES
        }
        settings = cls(
            provider=provider,
            default_model=default_model,
            base_url=base_url,
            api_key=api_key,
            agent_models=models,
            log_level=os.getenv("MIR_LOG_LEVEL", "INFO").upper(),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.provider not in SUPPORTED_PROVIDERS:
            raise ConfigurationError(
                f"Unsupported MIR_LLM_PROVIDER '{self.provider}'. "
                f"Expected one of: {', '.join(sorted(SUPPORTED_PROVIDERS))}"
            )
        if not self.default_model:
            raise ConfigurationError("MIR_LLM_MODEL cannot be empty")
        if self.provider == "groq" and not self.api_key:
            raise ConfigurationError("GROQ_API_KEY is required when MIR_LLM_PROVIDER=groq")
        if self.provider == "openai_compatible" and not self.base_url:
            raise ConfigurationError(
                "MIR_LLM_BASE_URL is required when MIR_LLM_PROVIDER=openai_compatible"
            )
