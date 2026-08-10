import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from mir_multiagent.cli import main
from mir_multiagent.ingestion import IngestionResult
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


if __name__ == "__main__":
    unittest.main()
