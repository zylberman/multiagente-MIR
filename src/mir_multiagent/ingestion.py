"""Fault-tolerant MIR PDF, question and embedded-image ingestion."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .models import MirQuestion, QuestionAsset, QuestionOption, normalized_source_name

LOGGER = logging.getLogger(__name__)
MARKER = re.compile(r"(?m)^\s*((?:\d{1,3})|[A-Ea-e])[\.:\)]\s+")
IMAGE_REFERENCE = re.compile(r"imagen\s*(?:n[º°o]\s*)?(\d+)?", re.IGNORECASE)


@dataclass(frozen=True)
class ExtractionIssue:
    code: str
    message: str
    source_page: int | None = None
    question_id: str | None = None
    severity: str = "warning"


@dataclass
class IngestionResult:
    questions: list[MirQuestion] = field(default_factory=list)
    assets: list[QuestionAsset] = field(default_factory=list)
    issues: list[ExtractionIssue] = field(default_factory=list)
    discarded_questions: int = 0

    @property
    def warning_count(self) -> int:
        return sum(issue.severity == "warning" for issue in self.issues) + sum(
            len(question.warnings) for question in self.questions
        )


def parse_questions(
    text: str,
    *,
    source_pdf: str | Path | None = None,
    source_page: int | None = None,
    assets: tuple[QuestionAsset, ...] = (),
) -> list[MirQuestion]:
    """Compatibility wrapper returning only successfully reconstructed questions."""
    return parse_questions_with_report(
        text,
        source_pdf=source_pdf,
        source_page=source_page,
        assets=assets,
    ).questions


def parse_questions_with_report(
    text: str,
    *,
    source_pdf: str | Path | None = None,
    source_page: int | None = None,
    assets: tuple[QuestionAsset, ...] = (),
) -> IngestionResult:
    """Reconstruct questions from option runs without aborting on malformed blocks.

    Question numbers and numeric option labels share the same lexical form. We first
    identify complete 1–4/1–5 or A–D/A–E option runs, then treat the immediately
    preceding marker as the question header. Ambiguous blocks are reported and
    skipped; later valid blocks remain available.
    """
    result = IngestionResult()
    markers = list(MARKER.finditer(text))
    runs = _find_option_runs(markers)
    consumed_question_markers: set[int] = set()
    consumed_markers: set[int] = set()

    for run_start, run_end in runs:
        header_index = run_start - 1
        if header_index < 0 or header_index in consumed_question_markers:
            result.discarded_questions += 1
            result.issues.append(
                ExtractionIssue(
                    code="missing-question-header",
                    message="Option sequence has no unambiguous preceding question header",
                    source_page=source_page,
                )
            )
            continue

        header = markers[header_index]
        question_id = header.group(1).upper()
        if not question_id.isdigit():
            result.discarded_questions += 1
            result.issues.append(
                ExtractionIssue(
                    code="invalid-question-id",
                    message="Question header is not numeric",
                    source_page=source_page,
                    question_id=question_id,
                )
            )
            continue

        stem = text[header.end() : markers[run_start].start()].strip()
        if not stem:
            result.discarded_questions += 1
            result.issues.append(
                ExtractionIssue(
                    code="empty-question-stem",
                    message="Question stem is empty after extraction",
                    source_page=source_page,
                    question_id=question_id,
                )
            )
            continue

        options: list[QuestionOption] = []
        raw_option_ids: list[str] = []
        malformed = False
        for marker_index in range(run_start, run_end + 1):
            marker = markers[marker_index]
            option_id = marker.group(1).upper()
            option_end = (
                markers[marker_index + 1].start()
                if marker_index + 1 < len(markers)
                else len(text)
            )
            option_text = text[marker.end() : option_end].strip()
            raw_option_ids.append(option_id)
            if not option_text:
                malformed = True
                result.issues.append(
                    ExtractionIssue(
                        code="empty-option",
                        message=f"Option {option_id} has no extracted text",
                        source_page=source_page,
                        question_id=question_id,
                    )
                )
                break
            options.append(QuestionOption(option_id, option_text))

        if malformed or len(raw_option_ids) != len(set(raw_option_ids)):
            result.discarded_questions += 1
            result.issues.append(
                ExtractionIssue(
                    code="ambiguous-option-sequence",
                    message=f"Question discarded; ambiguous option ids: {raw_option_ids}",
                    source_page=source_page,
                    question_id=question_id,
                )
            )
            continue

        block_end = markers[run_end + 1].start() if run_end + 1 < len(markers) else len(text)
        raw_block = text[header.start() : block_end].strip()
        image_match = IMAGE_REFERENCE.search(raw_block)
        question_assets, association_warnings = _associate_assets(
            image_match,
            assets,
            source_page=source_page,
        )
        warnings = list(association_warnings)
        if len(options) not in {4, 5}:
            warnings.append(f"unusual option count: {len(options)}")

        try:
            result.questions.append(
                MirQuestion(
                    question_id=question_id,
                    stem=stem,
                    options=tuple(options),
                    source_page=source_page,
                    source_pdf=normalized_source_name(source_pdf),
                    has_associated_image=image_match is not None,
                    assets=question_assets,
                    raw_extracted_text=raw_block,
                    warnings=tuple(warnings),
                    metadata={"extraction_confidence": "low" if warnings else "high"},
                )
            )
            consumed_question_markers.add(header_index)
            consumed_markers.add(header_index)
            consumed_markers.update(range(run_start, run_end + 1))
        except ValueError as exc:
            result.discarded_questions += 1
            result.issues.append(
                ExtractionIssue(
                    code="invalid-question-contract",
                    message=str(exc),
                    source_page=source_page,
                    question_id=question_id,
                    severity="error",
                )
            )
    for marker_index, marker in enumerate(markers[:-1]):
        next_label = markers[marker_index + 1].group(1).upper()
        if (
            marker_index not in consumed_markers
            and marker.group(1).isdigit()
            and next_label in {"1", "A"}
        ):
            result.discarded_questions += 1
            result.issues.append(
                ExtractionIssue(
                    code="unparsed-question-block",
                    message="Possible question block did not contain an unambiguous option sequence",
                    source_page=source_page,
                    question_id=marker.group(1),
                )
            )
    return result


def extract_questions_from_pdf(pdf_path: str | Path) -> list[MirQuestion]:
    """Compatibility wrapper returning questions without the extraction report."""
    return ingest_pdf(pdf_path).questions


def ingest_pdf(pdf_path: str | Path, image_output_dir: str | Path | None = None) -> IngestionResult:
    """Extract embedded images and parse all pages without one bad block aborting the PDF."""
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"Input PDF not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF input, got: {path.name}")
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required for PDF ingestion") from exc

    result = IngestionResult()
    output_dir = Path(image_output_dir) if image_output_dir else None
    with pdfplumber.open(path) as pdf:
        result.assets.extend(_extract_image_assets(pdf.pages, path, output_dir, result.issues))
        for page_number, page in enumerate(pdf.pages, start=1):
            page_assets = tuple(asset for asset in result.assets if asset.source_page == page_number)
            page_result = parse_questions_with_report(
                _extract_two_column_text(page),
                source_pdf=path,
                source_page=page_number,
                assets=page_assets,
            )
            result.questions.extend(page_result.questions)
            result.issues.extend(page_result.issues)
            result.discarded_questions += page_result.discarded_questions
    if not result.questions:
        result.issues.append(
            ExtractionIssue("no-questions", "No structured questions were detected", severity="error")
        )
    return result


def _find_option_runs(markers: list[re.Match[str]]) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    index = 0
    while index < len(markers):
        label = markers[index].group(1).upper()
        expected = ["1", "2", "3", "4"] if label == "1" else ["A", "B", "C", "D"] if label == "A" else []
        labels = [marker.group(1).upper() for marker in markers[index : index + 5]]
        if expected and labels[:4] == expected:
            end = index + 3
            fifth = "5" if label == "1" else "E"
            if len(labels) >= 5 and labels[4] == fifth:
                # A fifth marker followed immediately by a new 1/A is more likely a
                # question number than option 5/E; retain the conservative 4-option run.
                next_label = markers[index + 5].group(1).upper() if index + 5 < len(markers) else None
                if next_label not in {"1", "A"}:
                    end += 1
            runs.append((index, end))
            index = end + 1
        else:
            index += 1
    return runs


def _associate_assets(
    image_match: re.Match[str] | None,
    page_assets: tuple[QuestionAsset, ...],
    *,
    source_page: int | None,
) -> tuple[tuple[QuestionAsset, ...], tuple[str, ...]]:
    if image_match is None:
        return (), ()
    if page_assets:
        associated = tuple(
            replace(asset, association_confidence=0.6, warnings=asset.warnings + ("heuristic same-page association",))
            for asset in page_assets
        )
        return associated, ("image association is heuristic",)
    return (), ("associated image not found",)


def _extract_image_assets(
    pages: list[Any],
    source_pdf: Path,
    output_dir: Path | None,
    issues: list[ExtractionIssue],
) -> list[QuestionAsset]:
    assets: list[QuestionAsset] = []
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
    for page_number, page in enumerate(pages, start=1):
        for image_index, image in enumerate(page.images, start=1):
            asset_id = f"{source_pdf.stem}-p{page_number}-img{image_index}"
            local_path = (output_dir / f"{asset_id}.png") if output_dir else Path(f"{asset_id}.png")
            warnings: list[str] = []
            if output_dir:
                try:
                    bbox = (image["x0"], image["top"], image["x1"], image["bottom"])
                    page.crop(bbox).to_image(resolution=150).save(local_path, format="PNG")
                except Exception as exc:
                    warnings.append(f"image extraction failed: {type(exc).__name__}")
                    issues.append(
                        ExtractionIssue(
                            "image-extraction-failed",
                            f"Embedded image {asset_id} could not be written ({type(exc).__name__})",
                            source_page=page_number,
                        )
                    )
            assets.append(
                QuestionAsset(
                    asset_id=asset_id,
                    source_page=page_number,
                    local_path=str(local_path),
                    warnings=tuple(warnings),
                    metadata={"source_pdf": source_pdf.name, "image_index": image_index},
                )
            )
    return assets


def _extract_two_column_text(page: Any) -> str:
    try:
        midpoint = page.width / 2
        left = page.within_bbox((0, 0, midpoint, page.height)).extract_text() or ""
        right = page.within_bbox((midpoint, 0, page.width, page.height)).extract_text() or ""
        combined = f"{left}\n{right}".strip()
        return combined or (page.extract_text() or "")
    except Exception as exc:
        LOGGER.warning("Column extraction failed; using full-page text: %s", type(exc).__name__)
        return page.extract_text() or ""
