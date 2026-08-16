import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from mir_multiagent.cli import main
from mir_multiagent.ingestion import IngestionResult
from mir_multiagent.ingestion import ExtractionIssue
from mir_multiagent.models import MirQuestion, QuestionOption


class ValidationCliTests(unittest.TestCase):
    def test_validation_command_does_not_run_agents(self) -> None:
        question = MirQuestion(
            question_id="1",
            source_question_number=1,
            stem="Synthetic question",
            options=tuple(QuestionOption(str(i), f"Option {i}") for i in range(1, 5)),
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "audit.json"
            with patch("mir_multiagent.cli.ingest_pdf", return_value=IngestionResult(questions=[question])):
                stream = io.StringIO()
                with redirect_stdout(stream):
                    code = main([
                        "validate-extraction", "synthetic.pdf",
                        "--expected-questions", "1", "--output", str(output),
                    ])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.read_text())["questions"]["integrity_status"], "complete")
            self.assertIn("Integrity: COMPLETE", stream.getvalue())

    def test_debug_output_reports_issue_metadata_without_full_question_text(self) -> None:
        issue = ExtractionIssue(
            code="QUESTION_BOUNDARY_FAILURE", message="Synthetic diagnostic",
            source_page=12, source_column="right", question_id="47",
            fingerprint="abc123", preview="short synthetic preview",
            option_ids=("A", "B"), contains_detected_options=True,
        )
        ingestion = IngestionResult(issues=[issue], discarded_questions=1)
        with patch("mir_multiagent.cli.ingest_pdf", return_value=ingestion):
            stream = io.StringIO()
            with redirect_stdout(stream):
                code = main([
                    "validate-extraction", "synthetic.pdf", "--expected-questions", "210",
                    "--debug-extraction",
                ])
        self.assertEqual(code, 1)
        output = stream.getvalue()
        self.assertIn("page=12", output)
        self.assertIn("reason=QUESTION_BOUNDARY_FAILURE", output)
        self.assertNotIn("Synthetic diagnostic", output)

    def test_analyze_question_selects_source_number_and_writes_structured_output(self) -> None:
        question = MirQuestion(
            question_id="28", source_question_number=28, stem="Synthetic question",
            options=tuple(QuestionOption(str(i), f"Option {i}") for i in range(1, 5)),
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "question-28.json"
            with patch("mir_multiagent.cli.ingest_pdf", return_value=IngestionResult(questions=[question])):
                code = main([
                    "analyze-question", "synthetic.pdf", "--question-number", "28",
                    "--output", str(output),
                ])
            data = json.loads(output.read_text())
        self.assertEqual(code, 0)
        self.assertEqual(data["question_number"], 28)
        self.assertEqual(data["status"], "complete")
        self.assertEqual(len(data["option_analysis"]), 4)

    def test_official_key_preserves_predicted_and_official_status_separately(self) -> None:
        question = MirQuestion(
            question_id="9", source_question_number=9, stem="Synthetic question",
            options=tuple(QuestionOption(str(i), f"Option {i}") for i in range(1, 5)),
        )
        with tempfile.TemporaryDirectory() as directory:
            key = Path(directory) / "official.json"
            key.write_text(json.dumps({"9": {"official_answer": "2", "annulled": True}}))
            output = Path(directory) / "question-9.json"
            with patch("mir_multiagent.cli.ingest_pdf", return_value=IngestionResult(questions=[question])):
                code = main([
                    "analyze-question", "synthetic.pdf", "--question-number", "9",
                    "--official-key", str(key), "--output", str(output),
                ])
            data = json.loads(output.read_text())
        self.assertEqual(code, 0)
        self.assertEqual(data["answer"]["predicted_correct_option"], "1")
        self.assertEqual(data["answer"]["official_correct_option"], "2")
        self.assertTrue(data["review"]["officially_annulled"])


if __name__ == "__main__":
    unittest.main()
