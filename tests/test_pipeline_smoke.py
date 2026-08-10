import unittest

from mir_multiagent.config import Settings
from mir_multiagent.ingestion import parse_questions
from mir_multiagent.orchestrator import MultiAgentPipeline
from mir_multiagent.providers import MockProvider


class PipelineSmokeTests(unittest.TestCase):
    def test_end_to_end_with_explicit_non_medical_mock(self) -> None:
        question = parse_questions(
            "1. Synthetic question\n1. A\n2. B\n3. C\n4. D\n"
        )[0]
        settings = Settings(
            provider="mock",
            default_model="deterministic-demo",
            agent_models={
                name: "deterministic-demo"
                for name in ("answer", "pharmacology", "clinical", "terminology", "mnemonic")
            },
        )
        final = MultiAgentPipeline.create(settings, MockProvider()).run(question)
        self.assertEqual(final.status, "complete")
        self.assertEqual(len(final.agent_results), 5)
        self.assertIn("SMOKE_TEST_ONLY", final.final_answer_text)


if __name__ == "__main__":
    unittest.main()
