"""CLI for explanation runs and extraction-only MIR audits."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .audit import build_extraction_audit
from .config import ConfigurationError, Settings
from .ingestion import ingest_pdf
from .orchestrator import MultiAgentPipeline
from .providers import build_provider


def build_run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Explain MIR study questions with specialized agents")
    parser.add_argument("pdf", type=Path, help="Local MIR questionnaire PDF")
    parser.add_argument("--question-index", type=int, default=0, help="Zero-based parsed question index")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    return parser


def build_validation_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit structural extraction without calling an LLM")
    parser.add_argument("pdf", type=Path, help="Local complete MIR exam PDF")
    parser.add_argument("--expected-questions", type=int, default=210)
    parser.add_argument("--output", type=Path, help="Optional extraction-audit JSON path")
    parser.add_argument("--debug-extraction", action="store_true", help="Print only ambiguous block metadata")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "validate-extraction":
        return _validate_extraction(build_validation_parser().parse_args(arguments[1:]))
    return _run_agents(build_run_parser().parse_args(arguments))


def _validate_extraction(args: argparse.Namespace) -> int:
    try:
        image_dir = Path("data/images") / args.pdf.stem
        ingestion = ingest_pdf(args.pdf, image_output_dir=image_dir)
        audit = build_extraction_audit(ingestion, args.pdf.name, args.expected_questions)
        questions = audit.questions
        images = audit.images
        print("MIR extraction audit\n")
        print(f"Expected questions:       {questions.expected_questions}")
        print(f"Recovered questions:      {questions.recovered_questions}")
        print(f"Missing questions:        {len(questions.missing_question_numbers)}")
        print(f"Duplicate questions:      {len(questions.duplicate_question_numbers)}")
        print(f"Ambiguous blocks:         {questions.ambiguous_blocks}\n")
        print(f"Images extracted:         {images.images_extracted}")
        print(f"Image-referencing Qs:     {images.questions_referencing_images}")
        print(f"Associated image Qs:      {images.questions_with_assets}")
        print(f"Unresolved image Qs:      {len(images.image_questions_without_asset)}\n")
        print(f"Integrity: {questions.integrity_status.upper()}")
        if args.debug_extraction:
            for issue in audit.extraction_issues:
                print(
                    "issue "
                    f"question={issue['question_id'] or '?'} page={issue['source_page'] or '?'} "
                    f"column={issue['source_column'] or '?'} reason={issue['code']} "
                    f"fingerprint={issue['fingerprint'] or '?'} preview={issue['preview'] or '-'}"
                )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(audit.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0 if questions.integrity_status == "complete" else 1
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        logging.error("%s", exc)
        return 2


def _run_agents(args: argparse.Namespace) -> int:
    try:
        settings = Settings.from_env()
        logging.basicConfig(
            level=getattr(logging, settings.log_level, logging.INFO),
            format="%(levelname)s %(name)s: %(message)s",
        )
        image_dir = Path("data/images") / args.pdf.stem
        ingestion = ingest_pdf(args.pdf, image_output_dir=image_dir)
        questions = ingestion.questions
        logging.info(
            "Ingestion completed: questions=%d discarded=%d warnings=%d assets=%d",
            len(questions), ingestion.discarded_questions, ingestion.warning_count, len(ingestion.assets),
        )
        if not questions:
            raise RuntimeError("No structured questions were extracted from the PDF")
        if not 0 <= args.question_index < len(questions):
            raise IndexError(
                f"question-index {args.question_index} is outside the parsed range 0..{len(questions)-1}"
            )
        if settings.provider == "mock":
            logging.warning("Using smoke-test provider; output is not a medical answer")
        payload = json.dumps(
            MultiAgentPipeline.create(settings, build_provider(settings))
            .run(questions[args.question_index]).to_dict(),
            ensure_ascii=False,
            indent=2,
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload + "\n", encoding="utf-8")
        else:
            print(payload)
        return 0
    except (ConfigurationError, FileNotFoundError, IndexError, RuntimeError, ValueError) as exc:
        logging.error("%s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
