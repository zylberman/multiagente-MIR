"""Command-line entry point for the minimal P0 path."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .config import ConfigurationError, Settings
from .ingestion import extract_questions_from_pdf
from .orchestrator import MultiAgentPipeline
from .providers import build_provider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Explain MIR study questions with specialized agents")
    parser.add_argument("pdf", type=Path, help="Local MIR questionnaire PDF")
    parser.add_argument("--question-index", type=int, default=0, help="Zero-based parsed question index")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        settings = Settings.from_env()
        logging.basicConfig(
            level=getattr(logging, settings.log_level, logging.INFO),
            format="%(levelname)s %(name)s: %(message)s",
        )
        questions = extract_questions_from_pdf(args.pdf)
        if not questions:
            raise RuntimeError("No structured questions were extracted from the PDF")
        if not 0 <= args.question_index < len(questions):
            raise IndexError(
                f"question-index {args.question_index} is outside the parsed range 0..{len(questions)-1}"
            )
        if settings.provider == "mock":
            logging.warning("Using smoke-test provider; output is not a medical answer")
        pipeline = MultiAgentPipeline.create(settings, build_provider(settings))
        payload = json.dumps(
            pipeline.run(questions[args.question_index]).to_dict(),
            ensure_ascii=False,
            indent=2,
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload + "\n", encoding="utf-8")
            logging.info("Wrote output to %s", args.output)
        else:
            print(payload)
        return 0
    except (ConfigurationError, FileNotFoundError, IndexError, RuntimeError, ValueError) as exc:
        logging.error("%s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
