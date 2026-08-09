"""Conservative MIR PDF/text ingestion.

P0 intentionally uses layout-aware text extraction plus tolerant parsing. It emits
warnings rather than pretending that OCR and image association are solved.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from .models import MirQuestion, QuestionOption, normalized_source_name

LOGGER = logging.getLogger(__name__)
# A bare numeric question must begin a text block. This prevents numbered options
# such as ``1. option`` from being treated as separate questions.
QUESTION_START = re.compile(
    r"(?:\A|\n\s*\n)\s*(?:Pregunta\s+)?(\d{1,3})[\.:]\s+",
    re.MULTILINE,
)
OPTION_START = re.compile(r"(?m)^\s*([1-5A-Ea-e])[\.:\)]\s+")
IMAGE_REFERENCE = re.compile(r"imagen\s*(?:n[º°o]\s*)?(\d+)?", re.IGNORECASE)


def parse_questions(
    text: str,
    *,
    source_pdf: str | Path | None = None,
    source_page: int | None = None,
    image_paths: tuple[str, ...] = (),
) -> list[MirQuestion]:
    """Parse numbered questions with 2–5 numbered/lettered options.

    Unusual option counts are preserved and flagged. Blocks with fewer than two
    options are skipped because they cannot satisfy the core contract.
    """
    starts = list(QUESTION_START.finditer(text))
    questions: list[MirQuestion] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        block = text[match.end() : end].strip()
        option_matches = list(OPTION_START.finditer(block))
        if len(option_matches) < 2:
            LOGGER.warning("Skipping question %s: fewer than two options detected", match.group(1))
            continue

        stem = block[: option_matches[0].start()].strip()
        options: list[QuestionOption] = []
        for option_index, option_match in enumerate(option_matches):
            option_end = (
                option_matches[option_index + 1].start()
                if option_index + 1 < len(option_matches)
                else len(block)
            )
            option_text = block[option_match.end() : option_end].strip()
            if option_text:
                options.append(QuestionOption(option_match.group(1).upper(), option_text))

        warnings: list[str] = []
        if len(options) not in {4, 5}:
            warnings.append(f"unusual option count: {len(options)}")
        image_match = IMAGE_REFERENCE.search(block)
        has_image = image_match is not None
        associated = tuple(str(path) for path in image_paths) if has_image else ()
        if has_image and not associated:
            warnings.append("associated image not found")
        confidence = "high" if len(options) in {4, 5} and stem else "low"
        if confidence == "low":
            warnings.append("low-confidence extraction")

        questions.append(
            MirQuestion(
                question_id=match.group(1),
                stem=stem,
                options=tuple(options),
                source_page=source_page,
                source_pdf=normalized_source_name(source_pdf),
                has_associated_image=has_image,
                associated_image_paths=associated,
                raw_extracted_text=block,
                metadata={"extraction_confidence": confidence, "warnings": warnings},
            )
        )
    return questions


def extract_questions_from_pdf(pdf_path: str | Path) -> list[MirQuestion]:
    """Extract and parse questions page by page from a local PDF."""
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"Input PDF not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF input, got: {path.name}")
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required for PDF ingestion") from exc

    questions: list[MirQuestion] = []
    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = _extract_two_column_text(page)
            questions.extend(
                parse_questions(page_text, source_pdf=path, source_page=page_number)
            )
    if not questions:
        LOGGER.warning("No structured questions were detected in %s", path.name)
    return questions


def _extract_two_column_text(page: object) -> str:
    """Read left then right column; fall back to regular page extraction."""
    try:
        midpoint = page.width / 2
        left = page.within_bbox((0, 0, midpoint, page.height)).extract_text() or ""
        right = page.within_bbox((midpoint, 0, page.width, page.height)).extract_text() or ""
        combined = f"{left}\n{right}".strip()
        return combined or (page.extract_text() or "")
    except Exception as exc:  # pdf layout errors vary by source file
        LOGGER.warning("Column extraction failed; using full-page text: %s", exc)
        return page.extract_text() or ""
