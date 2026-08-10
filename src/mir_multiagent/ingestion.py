"""Traceable, fault-tolerant MIR PDF and embedded-image ingestion."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .models import MirQuestion, QuestionAsset, QuestionOption, normalized_source_name

LOGGER = logging.getLogger(__name__)
MARKER = re.compile(r"(?m)^\s*((?:\d{1,3})|[A-Ea-e])[\.:\)]\s+")
IMAGE_REFERENCE = re.compile(r"imagen(?:\s+asociada)?\s*(?:n[º°o]\s*)?(\d+)?", re.IGNORECASE)


@dataclass(frozen=True)
class SourceSpan:
    start: int
    end: int
    page: int
    column: str


@dataclass(frozen=True)
class ExtractionIssue:
    code: str
    message: str
    source_page: int | None = None
    source_column: str | None = None
    question_id: str | None = None
    severity: str = "warning"
    fingerprint: str | None = None
    preview: str | None = None
    option_ids: tuple[str, ...] = ()


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
    return parse_questions_with_report(
        text, source_pdf=source_pdf, source_page=source_page, assets=assets
    ).questions


def parse_questions_with_report(
    text: str,
    *,
    source_pdf: str | Path | None = None,
    source_page: int | None = None,
    assets: tuple[QuestionAsset, ...] = (),
    source_spans: tuple[SourceSpan, ...] = (),
) -> IngestionResult:
    """Reconstruct numbered questions from complete option runs.

    Numeric question numbers and option labels share syntax. Complete 1–4/1–5 or
    A–D/A–E runs are located first; the preceding numeric marker becomes the source
    question number. Ambiguous blocks produce issues and never abort later blocks.
    """
    result = IngestionResult()
    markers = list(MARKER.finditer(text))
    runs = _find_option_runs(markers)
    consumed: set[int] = set()

    for run_start, run_end in runs:
        header_index = run_start - 1
        header = markers[header_index] if header_index >= 0 else None
        page, column = _location_for_offset(
            header.start() if header else markers[run_start].start(), source_spans, source_page
        )
        if header is None or not header.group(1).isdigit() or header_index in consumed:
            result.discarded_questions += 1
            result.issues.append(
                _issue("QUESTION_BOUNDARY_FAILURE", "Option run has no unambiguous numeric header", text,
                       markers[run_start].start(), page, column, option_ids=_marker_ids(markers, run_start, run_end))
            )
            continue

        source_number = int(header.group(1))
        question_id = str(source_number)
        stem = text[header.end() : markers[run_start].start()].strip()
        if not stem:
            result.discarded_questions += 1
            result.issues.append(
                _issue("MISSING_STEM", "Question stem is empty", text, header.start(), page, column,
                       question_id=question_id, option_ids=_marker_ids(markers, run_start, run_end))
            )
            continue

        options: list[QuestionOption] = []
        option_ids = _marker_ids(markers, run_start, run_end)
        malformed = len(option_ids) != len(set(option_ids))
        for marker_index in range(run_start, run_end + 1):
            marker = markers[marker_index]
            option_end = markers[marker_index + 1].start() if marker_index + 1 < len(markers) else len(text)
            option_text = text[marker.end() : option_end].strip()
            if not option_text:
                malformed = True
                break
            options.append(QuestionOption(marker.group(1).upper(), option_text))
        if malformed:
            result.discarded_questions += 1
            result.issues.append(
                _issue("DUPLICATE_OPTION_ID", "Ambiguous or empty option sequence", text, header.start(),
                       page, column, question_id, option_ids)
            )
            continue

        block_end = markers[run_end + 1].start() if run_end + 1 < len(markers) else len(text)
        raw_block = text[header.start() : block_end].strip()
        pages = _pages_for_range(header.start(), block_end, source_spans, source_page)
        image_match = IMAGE_REFERENCE.search(raw_block)
        referenced_number = int(image_match.group(1)) if image_match and image_match.group(1) else None
        question_assets, association_warnings = _associate_assets(
            image_match, referenced_number, assets, pages
        )
        warnings = list(association_warnings)
        if len(pages) > 1:
            warnings.append("QUESTION_CONTINUED_ACROSS_PAGE")
        if len(options) not in {4, 5}:
            warnings.append(f"unusual option count: {len(options)}")
        try:
            result.questions.append(
                MirQuestion(
                    question_id=question_id,
                    source_question_number=source_number,
                    stem=stem,
                    options=tuple(options),
                    source_page=pages[0] if pages else page,
                    source_pages=pages,
                    source_column=column,
                    source_pdf=normalized_source_name(source_pdf),
                    has_associated_image=image_match is not None,
                    referenced_image_number=referenced_number,
                    assets=question_assets,
                    raw_extracted_text=raw_block,
                    warnings=tuple(warnings),
                    metadata={
                        "extraction_confidence": "low" if warnings else "high",
                        "provenance": {"pages": pages, "column": column},
                    },
                )
            )
            consumed.add(header_index)
            consumed.update(range(run_start, run_end + 1))
        except ValueError as exc:
            result.discarded_questions += 1
            result.issues.append(
                _issue("INVALID_QUESTION_CONTRACT", str(exc), text, header.start(), page, column,
                       question_id, option_ids, severity="error")
            )

    for index, marker in enumerate(markers[:-1]):
        if index in consumed:
            continue
        next_label = markers[index + 1].group(1).upper()
        if marker.group(1).isdigit() and next_label in {"1", "A"}:
            page, column = _location_for_offset(marker.start(), source_spans, source_page)
            result.discarded_questions += 1
            result.issues.append(
                _issue("UNRECOGNIZED_LAYOUT", "Possible question lacks a complete option sequence", text,
                       marker.start(), page, column, marker.group(1))
            )
    return result


def extract_questions_from_pdf(pdf_path: str | Path) -> list[MirQuestion]:
    return ingest_pdf(pdf_path).questions


def ingest_pdf(pdf_path: str | Path, image_output_dir: str | Path | None = None) -> IngestionResult:
    """Parse one continuous left→right, page→page stream and preserve provenance."""
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
        document_text, spans = _build_document_stream(pdf.pages)
    parsed = parse_questions_with_report(
        document_text, source_pdf=path, assets=tuple(result.assets), source_spans=spans
    )
    result.questions = parsed.questions
    result.issues.extend(parsed.issues)
    result.discarded_questions = parsed.discarded_questions
    if not result.questions:
        result.issues.append(
            ExtractionIssue("NO_QUESTIONS", "No structured questions were detected", severity="error")
        )
    return result


def _find_option_runs(markers: list[re.Match[str]]) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    index = 0
    while index < len(markers):
        label = markers[index].group(1).upper()
        expected = ["1", "2", "3", "4"] if label == "1" else ["A", "B", "C", "D"] if label == "A" else []
        labels = [marker.group(1).upper() for marker in markers[index : index + 6]]
        if expected and labels[:4] == expected:
            end = index + 3
            fifth = "5" if label == "1" else "E"
            if len(labels) >= 5 and labels[4] == fifth:
                next_label = labels[5] if len(labels) >= 6 else None
                if next_label not in {"1", "A"}:
                    end += 1
            runs.append((index, end))
            index = end + 1
        else:
            index += 1
    return runs


def _associate_assets(
    image_match: re.Match[str] | None,
    referenced_number: int | None,
    assets: tuple[QuestionAsset, ...],
    source_pages: tuple[int, ...],
) -> tuple[tuple[QuestionAsset, ...], tuple[str, ...]]:
    if image_match is None:
        return (), ()
    if referenced_number is not None:
        exact = tuple(asset for asset in assets if asset.source_image_number == referenced_number)
        if len(exact) == 1:
            return (replace(exact[0], association_confidence=1.0),), ()
        if len(exact) > 1:
            return (), ("multiple assets match referenced image number",)
        return (), ("referenced image number has no extracted asset",)
    nearby = tuple(asset for asset in assets if asset.source_page in source_pages)
    if len(nearby) == 1:
        return (replace(nearby[0], association_confidence=0.4,
                        warnings=nearby[0].warnings + ("heuristic same-page association",)),), (
            "image association is low-confidence",
        )
    return (), ("associated image not found",)


def _extract_image_assets(
    pages: list[Any], source_pdf: Path, output_dir: Path | None, issues: list[ExtractionIssue]
) -> list[QuestionAsset]:
    assets: list[QuestionAsset] = []
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
    image_number = 0
    for page_number, page in enumerate(pages, start=1):
        for image_index, image in enumerate(page.images, start=1):
            image_number += 1
            asset_id = f"{source_pdf.stem}-p{page_number}-img{image_index}"
            local_path = (output_dir / f"{asset_id}.png") if output_dir else Path(f"{asset_id}.png")
            warnings: list[str] = []
            if output_dir:
                try:
                    bbox = (image["x0"], image["top"], image["x1"], image["bottom"])
                    page.crop(bbox).to_image(resolution=150).save(local_path, format="PNG")
                except Exception as exc:
                    warnings.append(f"image extraction failed: {type(exc).__name__}")
                    issues.append(ExtractionIssue("IMAGE_EXTRACTION_FAILED", f"Asset {asset_id} was not written",
                                                  page_number, severity="warning"))
            assets.append(
                QuestionAsset(
                    asset_id=asset_id,
                    source_page=page_number,
                    source_image_number=image_number,
                    local_path=str(local_path),
                    warnings=tuple(warnings),
                    metadata={"source_pdf": source_pdf.name, "page_image_index": image_index},
                )
            )
    return assets


def _build_document_stream(pages: list[Any]) -> tuple[str, tuple[SourceSpan, ...]]:
    parts: list[str] = []
    spans: list[SourceSpan] = []
    offset = 0
    for page_number, page in enumerate(pages, start=1):
        for column, text in _extract_page_columns(page):
            if not text:
                continue
            if parts:
                parts.append("\n")
                offset += 1
            start = offset
            parts.append(text)
            offset += len(text)
            spans.append(SourceSpan(start, offset, page_number, column))
    return "".join(parts), tuple(spans)


def _extract_page_columns(page: Any) -> tuple[tuple[str, str], ...]:
    try:
        midpoint = page.width / 2
        left = page.within_bbox((0, 0, midpoint, page.height)).extract_text() or ""
        right = page.within_bbox((midpoint, 0, page.width, page.height)).extract_text() or ""
        if left or right:
            return (("left", left), ("right", right))
    except Exception as exc:
        LOGGER.warning("Column extraction failed; using full page: %s", type(exc).__name__)
    return (("full", page.extract_text() or ""),)


def _extract_two_column_text(page: Any) -> str:
    return "\n".join(text for _, text in _extract_page_columns(page) if text)


def _location_for_offset(
    offset: int, spans: tuple[SourceSpan, ...], fallback_page: int | None
) -> tuple[int | None, str | None]:
    for span in spans:
        if span.start <= offset < span.end:
            return span.page, span.column
    return fallback_page, None


def _pages_for_range(
    start: int, end: int, spans: tuple[SourceSpan, ...], fallback_page: int | None
) -> tuple[int, ...]:
    pages = tuple(dict.fromkeys(span.page for span in spans if span.start < end and span.end > start))
    return pages or ((fallback_page,) if fallback_page else ())


def _marker_ids(markers: list[re.Match[str]], start: int, end: int) -> tuple[str, ...]:
    return tuple(marker.group(1).upper() for marker in markers[start : end + 1])


def _issue(
    code: str, message: str, text: str, offset: int, page: int | None, column: str | None,
    question_id: str | None = None, option_ids: tuple[str, ...] = (), severity: str = "warning"
) -> ExtractionIssue:
    fragment = " ".join(text[offset : offset + 48].split())
    return ExtractionIssue(
        code=code,
        message=message,
        source_page=page,
        source_column=column,
        question_id=question_id,
        severity=severity,
        fingerprint=hashlib.sha256(fragment.encode("utf-8")).hexdigest()[:12],
        preview=fragment[:32] or None,
        option_ids=option_ids,
    )
