"""Prompt loading and validation."""

from __future__ import annotations

import json
from pathlib import Path

REQUIRED_PROMPTS = {"answer", "pharmacology", "clinical", "terminology", "mnemonic"}
DEFAULT_PATH = Path(__file__).parents[2] / "config" / "prompts.json"


def load_prompts(path: str | Path | None = None) -> dict[str, str]:
    prompt_path = Path(path) if path else DEFAULT_PATH
    try:
        data = json.loads(prompt_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Prompt configuration not found: {prompt_path}") from exc
    missing = REQUIRED_PROMPTS - data.keys()
    if missing:
        raise ValueError(f"Missing prompts: {', '.join(sorted(missing))}")
    if any(not isinstance(data[name], str) or not data[name].strip() for name in REQUIRED_PROMPTS):
        raise ValueError("Every agent prompt must be a non-empty string")
    return data
