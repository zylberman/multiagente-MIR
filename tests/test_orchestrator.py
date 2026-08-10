import unittest

from mir_multiagent.models import AgentResult, MirQuestion, QuestionOption
from mir_multiagent.orchestrator import assemble_final_explanation


class AssemblyTests(unittest.TestCase):
    def test_assembly_builds_final_contract(self) -> None:
        question = MirQuestion(
            question_id="7",
            stem="Synthetic question",
            options=(QuestionOption("1", "A"), QuestionOption("2", "B")),
        )
        results = tuple(
            AgentResult(agent_name=name, status="success", content=f"{name} output")
            for name in ("answer", "pharmacology", "clinical", "terminology", "mnemonic")
        )
        final = assemble_final_explanation(question, results)
        self.assertEqual(final.question_id, "7")
        self.assertEqual(final.status, "complete")
        self.assertEqual(final.clinical_explanation, "clinical output")
        self.assertEqual(final.mnemonic_visual_analogy, "mnemonic output")
        self.assertEqual(len(final.agent_results), 5)


class RecordingProvider:
    provider_name = "recording"

    def __init__(self, failing_model: str | None = None) -> None:
        self.failing_model = failing_model
        self.calls: list[tuple[str, str]] = []

    def complete(self, *, system_prompt: str, user_prompt: str, model: str) -> str:
        self.calls.append((model, user_prompt))
        if model == self.failing_model:
            raise TimeoutError("synthetic provider failure")
        return f"successful output from {model}"


class PipelineFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        from mir_multiagent.config import Settings

        self.question = MirQuestion(
            question_id="8",
            stem="Synthetic question",
            options=(QuestionOption("1", "A"), QuestionOption("2", "B")),
        )
        self.settings = Settings(
            provider="mock",
            default_model="default",
            agent_models={
                "answer": "answer-model",
                "pharmacology": "pharmacology-model",
                "clinical": "clinical-model",
                "terminology": "terminology-model",
                "mnemonic": "mnemonic-model",
            },
        )

    def test_answer_failure_stops_pipeline(self) -> None:
        from mir_multiagent.orchestrator import MultiAgentPipeline

        provider = RecordingProvider(failing_model="answer-model")
        final = MultiAgentPipeline.create(self.settings, provider).run(self.question)
        self.assertEqual(final.status, "failed")
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(final.agent_results[0].status, "failed")
        self.assertTrue(all(result.status == "skipped" for result in final.agent_results[1:]))

    def test_secondary_failure_produces_partial_without_reusing_failure(self) -> None:
        from mir_multiagent.orchestrator import MultiAgentPipeline

        provider = RecordingProvider(failing_model="pharmacology-model")
        final = MultiAgentPipeline.create(self.settings, provider).run(self.question)
        self.assertEqual(final.status, "partial")
        pharmacology = next(r for r in final.agent_results if r.agent_name == "pharmacology")
        self.assertEqual(pharmacology.status, "failed")
        self.assertEqual(pharmacology.content, "")
        later_prompts = [prompt for model, prompt in provider.calls if model != "pharmacology-model"]
        self.assertTrue(all("TimeoutError" not in prompt for prompt in later_prompts))


if __name__ == "__main__":
    unittest.main()
