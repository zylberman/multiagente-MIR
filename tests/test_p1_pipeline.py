import json
import tempfile
import unittest
from pathlib import Path

from mir_multiagent.config import Settings
from mir_multiagent.models import MirQuestion, QuestionAsset, QuestionOption
from mir_multiagent.p1_models import OfficialAnswer, ProviderCapabilities
from mir_multiagent.p1_pipeline import (
    P1Pipeline, StructuredOutputError, validate_option_analysis, validate_resolver,
)
from mir_multiagent.providers import MockProvider


def settings() -> Settings:
    return Settings(provider="mock", default_model="mock-p1", agent_models={})


def question(*, image_path: str | None = None) -> MirQuestion:
    assets = ()
    if image_path:
        assets = (QuestionAsset(
            "synthetic-image-1", source_image_number=1, local_path=image_path,
            association_confidence=1.0,
        ),)
    return MirQuestion(
        question_id="1", source_question_number=1, stem="Synthetic educational question",
        options=tuple(QuestionOption(str(i), f"Option {i}") for i in range(1, 5)),
        has_associated_image=bool(image_path), referenced_image_number=1 if image_path else None,
        assets=assets,
    )


class NoVisionProvider(MockProvider):
    capabilities = ProviderCapabilities(True, False, True)


class InvalidTaskProvider(MockProvider):
    def __init__(self, task: str) -> None:
        self.task = task
        self.called_tasks: list[str] = []

    def complete(self, *, system_prompt, user_prompt, model, images=()):
        task = system_prompt.splitlines()[0].split("=", 1)[1]
        self.called_tasks.append(task)
        if task == self.task:
            return "not-json"
        return super().complete(system_prompt=system_prompt, user_prompt=user_prompt, model=model, images=images)


class DisagreementProvider(MockProvider):
    def __init__(self, *, unresolved: bool = False, flags: bool = False) -> None:
        self.unresolved = unresolved
        self.flags = flags
        self.called_tasks: list[str] = []

    def complete(self, *, system_prompt, user_prompt, model, images=()):
        task = system_prompt.splitlines()[0].split("=", 1)[1]
        self.called_tasks.append(task)
        data = json.loads(super().complete(system_prompt=system_prompt, user_prompt=user_prompt, model=model, images=images))
        if task == "reviewer":
            data["predicted_correct_option"] = "2"
            data["multiple_answers_plausible"] = self.flags
            data["possible_invalid_question"] = self.flags
            data["candidate_options"] = ["1", "2"] if self.flags else []
            data["invalid_reasons"] = ["multiple_correct_answers"] if self.flags else []
        if task == "adjudicator" and self.unresolved:
            data["final_predicted_option"] = None
            data["unresolved_ambiguity"] = True
        return json.dumps(data)


class PromptRecordingProvider(MockProvider):
    def __init__(self) -> None:
        self.prompts: dict[str, str] = {}

    def complete(self, *, system_prompt, user_prompt, model, images=()):
        task = system_prompt.splitlines()[0].split("=", 1)[1]
        self.prompts[task] = user_prompt
        return super().complete(system_prompt=system_prompt, user_prompt=user_prompt, model=model, images=images)


class P1PipelineTests(unittest.TestCase):
    def test_text_only_complete_structured_output(self) -> None:
        final = P1Pipeline(settings(), MockProvider()).run(question())
        self.assertEqual(final.status, "complete")
        self.assertEqual(final.answer["predicted_correct_option"], "1")
        self.assertEqual(len(final.option_analysis), 4)
        self.assertEqual(len(final.high_yield_points), 3)
        self.assertTrue(final.terminology)
        self.assertTrue(final.scales_values_formulas)
        self.assertFalse(final.pharmacology.applies)
        self.assertTrue(final.mnemonic.associations)

    def test_image_bytes_reach_multimodal_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset.png"
            path.write_bytes(b"actual-image-content")
            provider = MockProvider()
            final = P1Pipeline(settings(), provider).run(question(image_path=str(path)))
            self.assertEqual(final.status, "complete")
            self.assertTrue(provider.received_images)
            self.assertEqual(provider.received_images[0].content, b"actual-image-content")

    def test_image_model_without_vision_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset.png"
            path.write_bytes(b"image")
            final = P1Pipeline(settings(), NoVisionProvider()).run(question(image_path=str(path)))
        self.assertEqual(final.status, "model_does_not_support_images")

    def test_missing_image_stops_before_provider(self) -> None:
        q = MirQuestion(
            question_id="1", source_question_number=1, stem="Synthetic image question",
            options=tuple(QuestionOption(str(i), f"Option {i}") for i in range(1, 5)),
            has_associated_image=True, warnings=("associated image not found",),
        )
        provider = MockProvider()
        final = P1Pipeline(settings(), provider).run(q)
        self.assertEqual(final.status, "missing_required_image")
        self.assertEqual(final.agent_trace, ())

    def test_invalid_resolver_json_causes_failed_result(self) -> None:
        final = P1Pipeline(settings(), InvalidTaskProvider("resolver")).run(question())
        self.assertEqual(final.status, "failed")
        self.assertIsNone(final.mnemonic)

    def test_reviewer_failure_causes_failed_result(self) -> None:
        final = P1Pipeline(settings(), InvalidTaskProvider("reviewer")).run(question())
        self.assertEqual(final.status, "failed")

    def test_specialist_failure_is_partial_and_skips_mnemonic(self) -> None:
        provider = InvalidTaskProvider("clinical")
        final = P1Pipeline(settings(), provider).run(question())
        self.assertEqual(final.status, "partial")
        self.assertIsNone(final.mnemonic)
        self.assertNotIn("mnemonic", provider.called_tasks)

    def test_agreement_does_not_call_adjudicator(self) -> None:
        provider = InvalidTaskProvider("never")
        final = P1Pipeline(settings(), provider).run(question())
        self.assertTrue(final.review["agreement"])
        self.assertNotIn("adjudicator", provider.called_tasks)

    def test_reviewer_is_independent_before_comparison(self) -> None:
        provider = PromptRecordingProvider()
        P1Pipeline(settings(), provider).run(question())
        reviewer_payload = provider.prompts["reviewer"]
        self.assertNotIn("predicted_correct_option", reviewer_payload)
        self.assertIn('"context": {}', reviewer_payload)

    def test_disagreement_calls_adjudicator(self) -> None:
        provider = DisagreementProvider()
        final = P1Pipeline(settings(), provider).run(question())
        self.assertFalse(final.review["agreement"])
        self.assertIn("adjudicator", provider.called_tasks)
        self.assertIsNotNone(final.review["adjudication"])

    def test_unresolved_adjudication_remains_explicit(self) -> None:
        final = P1Pipeline(settings(), DisagreementProvider(unresolved=True)).run(question())
        self.assertEqual(final.status, "partial")
        self.assertIsNone(final.answer["predicted_correct_option"])
        self.assertTrue(final.review["adjudication"]["unresolved_ambiguity"])

    def test_multiple_and_possible_invalid_flags_are_preserved(self) -> None:
        final = P1Pipeline(settings(), DisagreementProvider(flags=True)).run(question())
        self.assertTrue(final.review["possible_multiple_correct_answers"])
        self.assertTrue(final.review["potentially_invalid"])
        self.assertEqual(final.review["candidate_options"], ("1", "2"))

    def test_official_annulment_is_only_local_input(self) -> None:
        inferred = P1Pipeline(settings(), DisagreementProvider(flags=True)).run(question())
        official = P1Pipeline(settings(), MockProvider()).run(question(), OfficialAnswer("1", True))
        self.assertIsNone(inferred.review["officially_annulled"])
        self.assertTrue(official.review["officially_annulled"])
        self.assertEqual(official.answer["official_correct_option"], "1")


class StructuredValidationTests(unittest.TestCase):
    def valid_resolver(self):
        return {"predicted_correct_option": "1", "predicted_correct_text": "A", "confidence": 0.8, "question_type": "single_best_answer", "critical_clues": ["x"], "reasoning_summary": "y", "possible_ambiguity": False, "warnings": []}

    def test_nonexistent_option_is_rejected(self) -> None:
        data = self.valid_resolver(); data["predicted_correct_option"] = "9"
        with self.assertRaises(StructuredOutputError): validate_resolver(data, ("1", "2"))

    def test_confidence_out_of_range_is_rejected(self) -> None:
        data = self.valid_resolver(); data["confidence"] = 1.1
        with self.assertRaises(StructuredOutputError): validate_resolver(data, ("1", "2"))

    def test_missing_required_field_is_rejected(self) -> None:
        data = self.valid_resolver(); del data["reasoning_summary"]
        with self.assertRaises(StructuredOutputError): validate_resolver(data, ("1", "2"))

    def test_all_options_required_and_plausible_verdict_allowed(self) -> None:
        data = {"items": [
            {"option_id": "1", "verdict": "correct", "reason": "x"},
            {"option_id": "2", "verdict": "plausible_but_not_best", "reason": "y"},
        ]}
        result = validate_option_analysis(data, ("1", "2"), "1")
        self.assertEqual(result[1].verdict, "plausible_but_not_best")
        with self.assertRaises(StructuredOutputError):
            validate_option_analysis({"items": data["items"][:1]}, ("1", "2"), "1")

    def test_inconsistent_correct_verdict_is_rejected(self) -> None:
        data = {"items": [
            {"option_id": "1", "verdict": "incorrect", "reason": "x"},
            {"option_id": "2", "verdict": "correct", "reason": "y"},
        ]}
        with self.assertRaises(StructuredOutputError):
            validate_option_analysis(data, ("1", "2"), "1")

    def test_unknown_option_verdict_is_rejected(self) -> None:
        data = {"items": [
            {"option_id": "1", "verdict": "definitely", "reason": "x"},
            {"option_id": "2", "verdict": "incorrect", "reason": "y"},
        ]}
        with self.assertRaises(StructuredOutputError):
            validate_option_analysis(data, ("1", "2"), "1")


if __name__ == "__main__":
    unittest.main()
