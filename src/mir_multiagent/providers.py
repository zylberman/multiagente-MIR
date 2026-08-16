"""Small provider boundary shared by all specialized agents."""

from __future__ import annotations

import base64
import json
import re
from typing import Protocol

from .config import Settings
from .p1_models import ImagePayload, ProviderCapabilities


class LlmProvider(Protocol):
    provider_name: str
    capabilities: ProviderCapabilities

    def complete(
        self, *, system_prompt: str, user_prompt: str, model: str,
        images: tuple[ImagePayload, ...] = (),
    ) -> str: ...


class MockProvider:
    """Deterministic smoke-test backend; it does not produce medical answers."""

    provider_name = "mock"
    capabilities = ProviderCapabilities(True, True, True)
    received_images: tuple[ImagePayload, ...] = ()

    def complete(self, *, system_prompt: str, user_prompt: str, model: str,
                 images: tuple[ImagePayload, ...] = ()) -> str:
        self.received_images = images
        if "TASK=" in system_prompt:
            return _mock_structured_response(system_prompt, user_prompt)
        return "SMOKE_TEST_ONLY: provider call completed; no medical answer was generated."


class GroqProvider:
    provider_name = "groq"
    capabilities = ProviderCapabilities(True, True, True)

    def __init__(self, api_key: str) -> None:
        try:
            from groq import Groq
        except ImportError as exc:
            raise RuntimeError("Install the 'groq' project extra to use Groq") from exc
        self._client = Groq(api_key=api_key)

    def complete(self, *, system_prompt: str, user_prompt: str, model: str,
                 images: tuple[ImagePayload, ...] = ()) -> str:
        content: object = user_prompt
        if images:
            content = [{"type": "text", "text": user_prompt}] + [
                {"type": "image_url", "image_url": {"url": f"data:{image.mime_type};base64,{base64.b64encode(image.content).decode('ascii')}"}}
                for image in images
            ]
        response = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            temperature=0.1,
        )
        return response.choices[0].message.content or "No content returned by provider"


class OpenAICompatibleProvider:
    provider_name = "openai_compatible"
    capabilities = ProviderCapabilities(True, True, True)

    def __init__(self, *, base_url: str, api_key: str | None) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install the 'local' project extra for OpenAI-compatible servers") from exc
        self._client = OpenAI(base_url=base_url, api_key=api_key or "local-development-only")

    def complete(self, *, system_prompt: str, user_prompt: str, model: str,
                 images: tuple[ImagePayload, ...] = ()) -> str:
        content: object = user_prompt
        if images:
            content = [{"type": "text", "text": user_prompt}] + [
                {"type": "image_url", "image_url": {"url": f"data:{image.mime_type};base64,{base64.b64encode(image.content).decode('ascii')}"}}
                for image in images
            ]
        response = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
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


def _mock_structured_response(system_prompt: str, user_prompt: str) -> str:
    """Return deterministic valid educational structures without medical claims."""
    task = re.search(r"TASK=([a-z_]+)", system_prompt).group(1)  # type: ignore[union-attr]
    match = re.search(r"OPTION_IDS_JSON=(\[[^\n]+\])", user_prompt)
    option_ids = json.loads(match.group(1)) if match else ["1", "2", "3", "4"]
    chosen = option_ids[0]
    responses: dict[str, object] = {
        "resolver": {"predicted_correct_option": chosen, "predicted_correct_text": "Synthetic option", "confidence": 0.8, "question_type": "single_best_answer", "critical_clues": ["Synthetic clue"], "reasoning_summary": "Synthetic structured resolver output", "possible_ambiguity": False, "warnings": []},
        "reviewer": {"predicted_correct_option": chosen, "confidence": 0.78, "multiple_answers_plausible": False, "possible_invalid_question": False, "reasoning_summary": "Independent synthetic review", "challenged_options": [], "warnings": [], "candidate_options": [], "invalid_reasons": []},
        "clinical": {"content": "Synthetic clinical explanation"},
        "pharmacology": {"applies": False, "content": "", "mir_points": []},
        "concepts": {"terminology": [{"term": "Synthetic term", "simple_explanation": "Simple synthetic explanation", "why_it_matters_here": "It supports comprehension"}], "scales_values_formulas": [{"name": "Synthetic scale", "type": "scale", "simple_explanation": "Simple scale explanation", "formula": "", "values_in_question": "", "worked_example": "", "mir_interpretation": "Synthetic interpretation"}]},
        "options": {"items": [{"option_id": item, "verdict": "correct" if item == chosen else "incorrect", "reason": "Synthetic option analysis", "what_would_make_it_correct": "Different synthetic context" if item != chosen else "", "mir_trap": ""} for item in option_ids]},
        "high_yield": {"points": ["Synthetic high-yield point 1", "Synthetic high-yield point 2", "Synthetic high-yield point 3"]},
        "mnemonic": {"scene": "An exaggerated synthetic scene", "associations": [{"visual_element": "Giant key", "medical_fact": "Synthetic accepted fact"}], "one_line_recall": "Recall the giant key"},
        "adjudicator": {"final_predicted_option": chosen, "decision": "Synthetic adjudication", "confidence": 0.7, "unresolved_ambiguity": False},
    }
    return json.dumps(responses[task])
