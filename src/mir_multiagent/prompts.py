"""Prompt loading and validation."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

REQUIRED_PROMPTS = {"answer", "pharmacology", "clinical", "terminology", "mnemonic"}


def load_prompts(path: str | Path | None = None) -> dict[str, str]:
    try:
        if path:
            prompt_path = Path(path)
            prompt_text = prompt_path.read_text(encoding="utf-8")
        else:
            prompt_path = "mir_multiagent.resources/prompts.json"
            prompt_text = (
                resources.files("mir_multiagent.resources")
                .joinpath("prompts.json")
                .read_text(encoding="utf-8")
            )
        data = json.loads(prompt_text)
    except FileNotFoundError as exc:
        raise ValueError(f"Prompt configuration not found: {prompt_path}") from exc
    missing = REQUIRED_PROMPTS - data.keys()
    if missing:
        raise ValueError(f"Missing prompts: {', '.join(sorted(missing))}")
    if any(not isinstance(data[name], str) or not data[name].strip() for name in REQUIRED_PROMPTS):
        raise ValueError("Every agent prompt must be a non-empty string")
    return data
