"""Stable contracts shared by ingestion, agents and output assembly."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True)
class QuestionOption:
    option_id: str
    text: str

    def __post_init__(self) -> None:
        if not self.option_id.strip() or not self.text.strip():
            raise ValueError("Question options require a non-empty id and text")


@dataclass(frozen=True)
class QuestionAsset:
    asset_id: str
    asset_type: str = "image"
    source_page: int | None = None
    source_image_number: int | None = None
    local_path: str = ""
    extraction_method: str = "pdf-embedded-image"
    association_confidence: float | None = None
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("Question asset id cannot be empty")
        if not self.local_path.strip():
            raise ValueError("Question asset local_path cannot be empty")
        if self.association_confidence is not None and not 0 <= self.association_confidence <= 1:
            raise ValueError("association_confidence must be between 0 and 1")


@dataclass(frozen=True)
class MirQuestion:
    question_id: str
    stem: str
    options: tuple[QuestionOption, ...]
    source_question_number: int | None = None
    source_page: int | None = None
    source_pages: tuple[int, ...] = ()
    source_column: str | None = None
    source_pdf: str | None = None
    has_associated_image: bool = False
    referenced_image_number: int | None = None
    assets: tuple[QuestionAsset, ...] = ()
    raw_extracted_text: str = ""
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.question_id.strip():
            raise ValueError("question_id cannot be empty")
        if not self.stem.strip():
            raise ValueError("stem cannot be empty")
        if len(self.options) < 2:
            raise ValueError("A MIR question requires at least two options")
        option_ids = [option.option_id for option in self.options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("Question option ids must be unique")
        if self.has_associated_image and not self.assets and not self.warnings:
            raise ValueError("Questions with an unresolved image require an explicit warning")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentResult:
    agent_name: str
    status: Literal["success", "failed", "skipped"]
    content: str
    predicted_correct_option: str | None = None
    confidence: float | None = None
    evidence_notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    error_type: str | None = None
    model: str | None = None
    provider: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.agent_name.strip():
            raise ValueError("Agent results require agent_name")
        if self.status == "success" and not self.content.strip():
            raise ValueError("Successful agent results require content")
        if self.status == "failed" and not self.error_type:
            raise ValueError("Failed agent results require error_type")
        if self.status != "failed" and self.error_type:
            raise ValueError("Only failed agent results may include error_type")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True)
class FinalExplanation:
    question_id: str
    status: Literal["complete", "partial", "failed"]
    predicted_correct_option: str | None
    final_answer_text: str
    clinical_explanation: str
    pharmacology_explanation: str
    terminology_explanation: str
    incorrect_option_analysis: dict[str, str]
    mnemonic_visual_analogy: str
    confidence: float | None = None
    citations: tuple[str, ...] = ()
    evidence_notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    agent_results: tuple[AgentResult, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalized_source_name(path: str | Path | None) -> str | None:
    """Return only a source filename so local absolute paths do not leak."""
    return Path(path).name if path else None
