"""Small provider boundary shared by all specialized agents."""

from __future__ import annotations

from typing import Protocol

from .config import Settings


class LlmProvider(Protocol):
    provider_name: str

    def complete(self, *, system_prompt: str, user_prompt: str, model: str) -> str: ...


class MockProvider:
    """Deterministic smoke-test backend; it does not produce medical answers."""

    provider_name = "mock"

    def complete(self, *, system_prompt: str, user_prompt: str, model: str) -> str:
        return "SMOKE_TEST_ONLY: provider call completed; no medical answer was generated."


class GroqProvider:
    provider_name = "groq"

    def __init__(self, api_key: str) -> None:
        try:
            from groq import Groq
        except ImportError as exc:
            raise RuntimeError("Install the 'groq' project extra to use Groq") from exc
        self._client = Groq(api_key=api_key)

    def complete(self, *, system_prompt: str, user_prompt: str, model: str) -> str:
        response = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        return response.choices[0].message.content or "No content returned by provider"


class OpenAICompatibleProvider:
    provider_name = "openai_compatible"

    def __init__(self, *, base_url: str, api_key: str | None) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install the 'local' project extra for OpenAI-compatible servers") from exc
        self._client = OpenAI(base_url=base_url, api_key=api_key or "local-development-only")

    def complete(self, *, system_prompt: str, user_prompt: str, model: str) -> str:
        response = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        return response.choices[0].message.content or "No content returned by provider"


def build_provider(settings: Settings) -> LlmProvider:
    if settings.provider == "mock":
        return MockProvider()
    if settings.provider == "groq":
        return GroqProvider(settings.api_key or "")
    if settings.provider == "openai_compatible":
        return OpenAICompatibleProvider(base_url=settings.base_url or "", api_key=settings.api_key)
    raise ValueError(f"Unsupported provider: {settings.provider}")
