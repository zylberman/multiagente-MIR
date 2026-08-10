"""Structural reconciliation for complete MIR exam extraction."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Literal

from .ingestion import IngestionResult
from .models import MirQuestion


@dataclass(frozen=True)
class QuestionReconciliation:
    expected_questions: int
    recovered_questions: int
    unique_question_numbers: int
    missing_question_numbers: tuple[int, ...]
    duplicate_question_numbers: tuple[int, ...]
    unexpected_question_numbers: tuple[int, ...]
    questions_without_source_number: tuple[str, ...]
    ambiguous_blocks: int
    integrity_status: Literal["complete", "incomplete", "suspicious"]


@dataclass(frozen=True)
class ImageReconciliation:
    images_extracted: int
    questions_referencing_images: int
    questions_with_assets: int
    high_confidence_associations: int
    low_confidence_associations: int
    image_questions_without_asset: tuple[int | str, ...]
    unassociated_assets: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ExtractionAudit:
    source_pdf: str
    questions: QuestionReconciliation
    images: ImageReconciliation
    extraction_issues: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def reconcile_questions(
    questions: list[MirQuestion], expected_questions: int, ambiguous_blocks: int = 0
) -> QuestionReconciliation:
    if expected_questions < 1:
        raise ValueError("expected_questions must be a positive integer")
    numbers = [question.source_question_number for question in questions if question.source_question_number is not None]
    counts = Counter(numbers)
    expected = set(range(1, expected_questions + 1))
    recovered = set(numbers)
    missing = tuple(sorted(expected - recovered))
    duplicates = tuple(sorted(number for number, count in counts.items() if count > 1))
    unexpected = tuple(sorted(recovered - expected))
    without_number = tuple(question.question_id for question in questions if question.source_question_number is None)
    if duplicates or unexpected or len(questions) > expected_questions:
        status: Literal["complete", "incomplete", "suspicious"] = "suspicious"
    elif missing or without_number:
        status = "incomplete"
    else:
        status = "complete"
    return QuestionReconciliation(
        expected_questions=expected_questions,
        recovered_questions=len(questions),
        unique_question_numbers=len(counts),
        missing_question_numbers=missing,
        duplicate_question_numbers=duplicates,
        unexpected_question_numbers=unexpected,
        questions_without_source_number=without_number,
        ambiguous_blocks=ambiguous_blocks,
        integrity_status=status,
    )


def reconcile_images(ingestion: IngestionResult) -> ImageReconciliation:
    referencing = [question for question in ingestion.questions if question.has_associated_image]
    with_assets = [question for question in referencing if question.assets]
    high = sum(
        1 for question in with_assets
        if max((asset.association_confidence or 0) for asset in question.assets) >= 0.8
    )
    low = sum(
        1 for question in with_assets
        if 0 < max((asset.association_confidence or 0) for asset in question.assets) < 0.8
    )
    unresolved = tuple(
        question.source_question_number or question.question_id
        for question in referencing if not question.assets
    )
    associated_ids = {asset.asset_id for question in with_assets for asset in question.assets}
    unassociated = tuple(asset.asset_id for asset in ingestion.assets if asset.asset_id not in associated_ids)
    warnings = () if 20 <= len(ingestion.assets) <= 35 else ("IMAGE_COUNT_OUTSIDE_EXPECTED_RANGE",)
    return ImageReconciliation(
        images_extracted=len(ingestion.assets),
        questions_referencing_images=len(referencing),
        questions_with_assets=len(with_assets),
        high_confidence_associations=high,
        low_confidence_associations=low,
        image_questions_without_asset=unresolved,
        unassociated_assets=unassociated,
        warnings=warnings,
    )


def build_extraction_audit(
    ingestion: IngestionResult, source_pdf: str, expected_questions: int
) -> ExtractionAudit:
    return ExtractionAudit(
        source_pdf=source_pdf,
        questions=reconcile_questions(
            ingestion.questions, expected_questions, ingestion.discarded_questions
        ),
        images=reconcile_images(ingestion),
        extraction_issues=tuple(asdict(issue) for issue in ingestion.issues),
    )
