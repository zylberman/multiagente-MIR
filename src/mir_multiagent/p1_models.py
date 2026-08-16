"""Typed contracts for one-question P1 educational analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .models import MirQuestion


AnalysisStatus = Literal[
    "complete", "partial", "failed", "missing_required_image",
    "needs_asset_review", "model_does_not_support_images", "needs_adjudication",
]


@dataclass(frozen=True)
class ProviderCapabilities:
    supports_text: bool = True
    supports_images: bool = False
    supports_structured_output: bool = False


@dataclass(frozen=True)
class ImagePayload:
    asset_id: str
    mime_type: str
    content: bytes = field(repr=False)
    source_image_number: int | None = None
    association_confidence: float = 0.0

    def __post_init__(self) -> None:
        if not self.content:
            raise ValueError("ImagePayload requires actual image bytes")
        if not 0 <= self.association_confidence <= 1:
            raise ValueError("association_confidence must be between 0 and 1")


@dataclass(frozen=True)
class QuestionPackage:
    question_number: int | None
    stem: str
    options: tuple[dict[str, str], ...]
    source_pages: tuple[int, ...]
    has_image_reference: bool
    referenced_image_number: int | None
    images: tuple[ImagePayload, ...]
    image_association_confidence: float | None
    extraction_warnings: tuple[str, ...]
    source_metadata: dict[str, Any]


@dataclass(frozen=True)
class PackageGateResult:
    status: AnalysisStatus
    package: QuestionPackage | None
    warnings: tuple[str, ...] = ()


def build_question_package(
    question: MirQuestion, *, minimum_image_confidence: float = 0.8
) -> PackageGateResult:
    """Load real image bytes and enforce conservative image association gates."""
    if not question.has_associated_image:
        return PackageGateResult("complete", _package(question, (), None))
    if not question.assets:
        return PackageGateResult(
            "missing_required_image", None,
            ("Question references an image but no associated asset is available",),
        )
    confidence = max((asset.association_confidence or 0.0) for asset in question.assets)
    if confidence < minimum_image_confidence:
        return PackageGateResult(
            "needs_asset_review", None,
            (f"Image association confidence {confidence:.2f} is below {minimum_image_confidence:.2f}",),
        )
    payloads: list[ImagePayload] = []
    for asset in question.assets:
        path = Path(asset.local_path)
        try:
            content = path.read_bytes()
        except OSError:
            return PackageGateResult(
                "missing_required_image", None,
                (f"Associated asset is unavailable: {asset.asset_id}",),
            )
        suffix = path.suffix.lower()
        mime_type = "image/png" if suffix == ".png" else "image/jpeg" if suffix in {".jpg", ".jpeg"} else "application/octet-stream"
        payloads.append(
            ImagePayload(
                asset_id=asset.asset_id,
                mime_type=mime_type,
                content=content,
                source_image_number=asset.source_image_number,
                association_confidence=asset.association_confidence or 0.0,
            )
        )
    return PackageGateResult("complete", _package(question, tuple(payloads), confidence))


def _package(
    question: MirQuestion, images: tuple[ImagePayload, ...], confidence: float | None
) -> QuestionPackage:
    pages = question.source_pages or ((question.source_page,) if question.source_page else ())
    return QuestionPackage(
        question_number=question.source_question_number,
        stem=question.stem,
        options=tuple({"option_id": item.option_id, "text": item.text} for item in question.options),
        source_pages=pages,
        has_image_reference=question.has_associated_image,
        referenced_image_number=question.referenced_image_number,
        images=images,
        image_association_confidence=confidence,
        extraction_warnings=question.warnings,
        source_metadata={"source_pdf": question.source_pdf, **question.metadata},
    )


@dataclass(frozen=True)
class ResolverResult:
    predicted_correct_option: str
    predicted_correct_text: str
    confidence: float
    question_type: str
    critical_clues: tuple[str, ...]
    reasoning_summary: str
    possible_ambiguity: bool = False
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class OptionAnalysis:
    option_id: str
    verdict: Literal["correct", "incorrect", "plausible_but_not_best", "ambiguous"]
    reason: str
    what_would_make_it_correct: str = ""
    mir_trap: str = ""


@dataclass(frozen=True)
class ReviewerResult:
    predicted_correct_option: str
    confidence: float
    multiple_answers_plausible: bool
    possible_invalid_question: bool
    reasoning_summary: str
    challenged_options: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    candidate_options: tuple[str, ...] = ()
    invalid_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdjudicationResult:
    final_predicted_option: str | None
    decision: str
    confidence: float
    unresolved_ambiguity: bool


@dataclass(frozen=True)
class ConceptExplanation:
    term: str
    simple_explanation: str
    why_it_matters_here: str


@dataclass(frozen=True)
class ScaleValueFormula:
    name: str
    type: str
    simple_explanation: str
    formula: str = ""
    values_in_question: str = ""
    worked_example: str = ""
    mir_interpretation: str = ""


@dataclass(frozen=True)
class PharmacologyResult:
    applies: bool
    content: str
    mir_points: tuple[str, ...] = ()


@dataclass(frozen=True)
class MnemonicAssociation:
    visual_element: str
    medical_fact: str


@dataclass(frozen=True)
class MnemonicResult:
    scene: str
    associations: tuple[MnemonicAssociation, ...]
    one_line_recall: str


@dataclass(frozen=True)
class AgentTrace:
    agent_name: str
    provider: str
    model: str
    status: str
    duration_ms: int
    error_type: str | None = None


@dataclass(frozen=True)
class OfficialAnswer:
    correct_option: str | None = None
    annulled: bool | None = None


@dataclass(frozen=True)
class FinalStudyExplanation:
    question_number: int | None
    status: AnalysisStatus
    question: dict[str, Any]
    answer: dict[str, Any]
    why_correct: str
    option_analysis: tuple[OptionAnalysis, ...]
    clinical_explanation: str
    pharmacology: PharmacologyResult
    terminology: tuple[ConceptExplanation, ...]
    scales_values_formulas: tuple[ScaleValueFormula, ...]
    high_yield_points: tuple[str, ...]
    mnemonic: MnemonicResult | None
    review: dict[str, Any]
    warnings: tuple[str, ...]
    agent_trace: tuple[AgentTrace, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
