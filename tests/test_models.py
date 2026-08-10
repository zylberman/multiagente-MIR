import unittest

from mir_multiagent.models import AgentResult, MirQuestion, QuestionAsset, QuestionOption


class MirQuestionTests(unittest.TestCase):
    def test_valid_question_contract(self) -> None:
        question = MirQuestion(
            question_id="12",
            stem="¿Cuál es la mejor opción?",
            options=(
                QuestionOption("1", "Primera"),
                QuestionOption("2", "Segunda"),
                QuestionOption("3", "Tercera"),
                QuestionOption("4", "Cuarta"),
            ),
            source_page=3,
            source_pdf="synthetic.pdf",
        )
        self.assertEqual(question.question_id, "12")
        self.assertEqual(len(question.options), 4)

    def test_question_rejects_too_few_options(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least two options"):
            MirQuestion(
                question_id="1",
                stem="Incomplete",
                options=(QuestionOption("1", "Only option"),),
            )

    def test_question_asset_contract(self) -> None:
        asset = QuestionAsset(
            asset_id="asset-1",
            source_page=4,
            local_path="ignored/local.png",
            association_confidence=0.5,
        )
        self.assertEqual(asset.asset_type, "image")

    def test_failed_agent_result_has_no_medical_content(self) -> None:
        result = AgentResult(
            agent_name="clinical",
            status="failed",
            content="",
            error_type="TimeoutError",
            model="test-model",
            provider="test-provider",
        )
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.content, "")


if __name__ == "__main__":
    unittest.main()
