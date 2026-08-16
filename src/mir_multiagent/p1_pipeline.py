"""Structured, multimodal, one-question P1 analysis pipeline."""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any, Callable

from .config import Settings
from .models import MirQuestion
from .p1_models import (
    AdjudicationResult, AgentTrace, ConceptExplanation, FinalStudyExplanation,
    MnemonicAssociation, MnemonicResult, OfficialAnswer, OptionAnalysis,
    PharmacologyResult, QuestionPackage, ResolverResult, ReviewerResult,
    ScaleValueFormula, build_question_package,
)
from .providers import LlmProvider


class StructuredOutputError(ValueError):
    """Provider output did not satisfy the required P1 contract."""


class P1Pipeline:
    def __init__(self, settings: Settings, provider: LlmProvider) -> None:
        self.settings = settings
        self.provider = provider
        self.trace: list[AgentTrace] = []

    def run(
        self, question: MirQuestion, official_answer: OfficialAnswer | None = None
    ) -> FinalStudyExplanation:
        self.trace = []
        gate = build_question_package(question)
        if gate.package is None:
            return self._terminal(question, gate.status, gate.warnings, official_answer)
        package = gate.package
        capabilities = self.provider.capabilities
        if not capabilities.supports_text or not capabilities.supports_structured_output:
            return self._terminal(
                question, "failed", ("Provider lacks required text or structured-output capability",),
                official_answer,
            )
        if package.images and not capabilities.supports_images:
            return self._terminal(
                question, "model_does_not_support_images",
                ("Configured provider/model does not support image input",), official_answer,
            )

        try:
            resolver = self._call("resolver", package, validate_resolver)
            # Independent by construction: reviewer receives only the original package.
            reviewer = self._call("reviewer", package, validate_reviewer)
        except Exception as exc:
            return self._terminal(question, "failed", (str(exc),), official_answer)

        specialist_errors: list[str] = []
        clinical = ""
        pharmacology = PharmacologyResult(False, "")
        terminology: tuple[ConceptExplanation, ...] = ()
        scales: tuple[ScaleValueFormula, ...] = ()
        option_analysis: tuple[OptionAnalysis, ...] = ()
        high_yield: tuple[str, ...] = ()
        specialist_calls: tuple[tuple[str, Callable[[dict[str, Any], tuple[str, ...]], Any]], ...] = (
            ("clinical", validate_clinical),
            ("pharmacology", validate_pharmacology),
            ("concepts", validate_concepts),
            ("options", lambda data, ids: validate_option_analysis(data, ids, resolver.predicted_correct_option)),
            ("high_yield", validate_high_yield),
        )
        for task, validator in specialist_calls:
            try:
                value = self._call(task, package, validator, resolver=resolver)
                if task == "clinical": clinical = value
                elif task == "pharmacology": pharmacology = value
                elif task == "concepts": terminology, scales = value
                elif task == "options": option_analysis = value
                elif task == "high_yield": high_yield = value
            except Exception as exc:
                specialist_errors.append(f"{task}: {exc}")

        agreement = resolver.predicted_correct_option == reviewer.predicted_correct_option
        adjudication: AdjudicationResult | None = None
        final_option: str | None = resolver.predicted_correct_option
        if not agreement:
            try:
                adjudication = self._call(
                    "adjudicator", package, validate_adjudication,
                    resolver=resolver, reviewer=reviewer,
                )
                final_option = adjudication.final_predicted_option
            except Exception as exc:
                specialist_errors.append(f"adjudicator: {exc}")
                final_option = None

        mnemonic: MnemonicResult | None = None
        medical_content_complete = bool(
            clinical and option_analysis and high_yield and not specialist_errors
        )
        if medical_content_complete:
            try:
                mnemonic = self._call(
                    "mnemonic", package, validate_mnemonic, resolver=resolver,
                    accepted_facts={"clinical": clinical, "high_yield": high_yield},
                )
            except Exception as exc:
                specialist_errors.append(f"mnemonic: {exc}")

        unresolved = bool(adjudication and adjudication.unresolved_ambiguity) or (
            not agreement and adjudication is None
        )
        status = "partial" if specialist_errors or unresolved else "complete"
        option_text = next(
            (item["text"] for item in package.options if item["option_id"] == final_option), ""
        )
        official = official_answer or OfficialAnswer()
        return FinalStudyExplanation(
            question_number=package.question_number,
            status=status,
            question=_question_summary(package),
            answer={
                "predicted_correct_option": final_option,
                "predicted_correct_text": option_text or resolver.predicted_correct_text,
                "confidence": adjudication.confidence if adjudication else resolver.confidence,
                "official_correct_option": official.correct_option,
            },
            why_correct=resolver.reasoning_summary,
            option_analysis=option_analysis,
            clinical_explanation=clinical,
            pharmacology=pharmacology,
            terminology=terminology,
            scales_values_formulas=scales,
            high_yield_points=high_yield,
            mnemonic=mnemonic,
            review={
                "reviewer_answer": reviewer.predicted_correct_option,
                "agreement": agreement,
                "possible_multiple_correct_answers": reviewer.multiple_answers_plausible,
                "candidate_options": reviewer.candidate_options,
                "potentially_invalid": reviewer.possible_invalid_question,
                "invalid_reasons": reviewer.invalid_reasons,
                "officially_annulled": official.annulled,
                "adjudication": asdict(adjudication) if adjudication else None,
            },
            warnings=package.extraction_warnings + tuple(specialist_errors),
            agent_trace=tuple(self.trace),
        )

    def _call(
        self, task: str, package: QuestionPackage,
        validator: Callable[[dict[str, Any], tuple[str, ...]], Any], **context: Any,
    ) -> Any:
        start = time.perf_counter()
        model = self.settings.agent_models.get(
            "answer" if task in {"resolver", "reviewer", "adjudicator", "options", "high_yield"} else
            "terminology" if task == "concepts" else task,
            self.settings.default_model,
        )
        try:
            raw = self.provider.complete(
                system_prompt=_task_prompt(task),
                user_prompt=_render_package(package, context),
                model=model,
                images=package.images,
            )
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError) as exc:
                raise StructuredOutputError(f"{task} returned invalid JSON") from exc
            if not isinstance(data, dict):
                raise StructuredOutputError(f"{task} output must be a JSON object")
            value = validator(data, tuple(item["option_id"] for item in package.options))
        except Exception as exc:
            self.trace.append(_trace(task, self.provider.provider_name, model, start, "failed", type(exc).__name__))
            raise
        self.trace.append(_trace(task, self.provider.provider_name, model, start, "success"))
        return value

    def _terminal(
        self, question: MirQuestion, status: str, warnings: tuple[str, ...],
        official_answer: OfficialAnswer | None,
    ) -> FinalStudyExplanation:
        official = official_answer or OfficialAnswer()
        return FinalStudyExplanation(
            question_number=question.source_question_number,
            status=status,  # type: ignore[arg-type]
            question={"stem": question.stem, "options": [asdict(x) for x in question.options], "image": {"required": question.has_associated_image, "asset_id": None}},
            answer={"predicted_correct_option": None, "predicted_correct_text": "", "confidence": None, "official_correct_option": official.correct_option},
            why_correct="", option_analysis=(), clinical_explanation="",
            pharmacology=PharmacologyResult(False, ""), terminology=(),
            scales_values_formulas=(), high_yield_points=(), mnemonic=None,
            review={"reviewer_answer": None, "agreement": None, "possible_multiple_correct_answers": None, "potentially_invalid": status == "missing_required_image", "officially_annulled": official.annulled},
            warnings=warnings, agent_trace=tuple(self.trace),
        )


def _required(data: dict[str, Any], fields: set[str]) -> None:
    missing = fields - data.keys()
    if missing:
        raise StructuredOutputError(f"Missing required fields: {', '.join(sorted(missing))}")


def _confidence(value: Any) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 1:
        raise StructuredOutputError("confidence must be between 0 and 1")
    return float(value)


def _option(value: Any, option_ids: tuple[str, ...]) -> str:
    if not isinstance(value, str) or value not in option_ids:
        raise StructuredOutputError("predicted option does not exist in the question")
    return value


def validate_resolver(data: dict[str, Any], option_ids: tuple[str, ...]) -> ResolverResult:
    _required(data, {"predicted_correct_option", "predicted_correct_text", "confidence", "question_type", "critical_clues", "reasoning_summary", "possible_ambiguity", "warnings"})
    predicted_text = str(data["predicted_correct_text"])
    reasoning = str(data["reasoning_summary"])
    if not predicted_text.strip() or not reasoning.strip():
        raise StructuredOutputError("resolver prediction text and reasoning are required")
    return ResolverResult(
        _option(data["predicted_correct_option"], option_ids), predicted_text,
        _confidence(data["confidence"]), str(data["question_type"]),
        tuple(str(x) for x in data["critical_clues"]), reasoning,
        bool(data["possible_ambiguity"]), tuple(str(x) for x in data["warnings"]),
    )


def validate_reviewer(data: dict[str, Any], option_ids: tuple[str, ...]) -> ReviewerResult:
    _required(data, {"predicted_correct_option", "confidence", "multiple_answers_plausible", "possible_invalid_question", "reasoning_summary"})
    candidates = tuple(str(x) for x in data.get("candidate_options", []))
    if any(x not in option_ids for x in candidates):
        raise StructuredOutputError("reviewer candidate option does not exist")
    if bool(data["multiple_answers_plausible"]) and len(candidates) < 2:
        raise StructuredOutputError("multiple-answer review requires at least two candidate options")
    invalid_reasons = tuple(str(x) for x in data.get("invalid_reasons", []))
    if bool(data["possible_invalid_question"]) and not invalid_reasons:
        raise StructuredOutputError("possible-invalid review requires explicit reasons")
    return ReviewerResult(
        _option(data["predicted_correct_option"], option_ids), _confidence(data["confidence"]),
        bool(data["multiple_answers_plausible"]), bool(data["possible_invalid_question"]),
        str(data["reasoning_summary"]), tuple(str(x) for x in data.get("challenged_options", [])),
        tuple(str(x) for x in data.get("warnings", [])), candidates,
        invalid_reasons,
    )


def validate_option_analysis(
    data: dict[str, Any], option_ids: tuple[str, ...], predicted: str
) -> tuple[OptionAnalysis, ...]:
    items = data.get("items")
    if not isinstance(items, list):
        raise StructuredOutputError("option analysis requires items")
    analyses = tuple(OptionAnalysis(**item) for item in items)
    allowed = {"correct", "incorrect", "plausible_but_not_best", "ambiguous"}
    if any(item.verdict not in allowed or not item.reason.strip() for item in analyses):
        raise StructuredOutputError("option analysis contains an invalid verdict or empty reason")
    if tuple(item.option_id for item in analyses) != option_ids:
        raise StructuredOutputError("every option must be analyzed exactly once and in source order")
    correct = tuple(item.option_id for item in analyses if item.verdict == "correct")
    if correct != (predicted,):
        raise StructuredOutputError("option verdicts are inconsistent with resolver prediction")
    return analyses


def validate_clinical(data: dict[str, Any], _: tuple[str, ...]) -> str:
    if not isinstance(data.get("content"), str) or not data["content"].strip():
        raise StructuredOutputError("clinical content is required")
    return data["content"]


def validate_pharmacology(data: dict[str, Any], _: tuple[str, ...]) -> PharmacologyResult:
    _required(data, {"applies", "content"})
    applies = bool(data["applies"])
    content = str(data["content"])
    if applies and not content.strip():
        raise StructuredOutputError("pharmacology content is required when applies=true")
    return PharmacologyResult(applies, content, tuple(str(x) for x in data.get("mir_points", [])))


def validate_concepts(data: dict[str, Any], _: tuple[str, ...]) -> tuple[tuple[ConceptExplanation, ...], tuple[ScaleValueFormula, ...]]:
    _required(data, {"terminology", "scales_values_formulas"})
    return (
        tuple(ConceptExplanation(**item) for item in data["terminology"]),
        tuple(ScaleValueFormula(**item) for item in data["scales_values_formulas"]),
    )


def validate_high_yield(data: dict[str, Any], _: tuple[str, ...]) -> tuple[str, ...]:
    points = tuple(str(x) for x in data.get("points", []))
    if not 3 <= len(points) <= 7 or any(not point.strip() for point in points):
        raise StructuredOutputError("high-yield output requires 3 to 7 non-empty points")
    return points


def validate_mnemonic(data: dict[str, Any], _: tuple[str, ...]) -> MnemonicResult:
    _required(data, {"scene", "associations", "one_line_recall"})
    associations = tuple(MnemonicAssociation(**item) for item in data["associations"])
    if not associations or any(not item.visual_element.strip() or not item.medical_fact.strip() for item in associations):
        raise StructuredOutputError("mnemonic requires explicit visual-to-medical mappings")
    scene, recall = str(data["scene"]), str(data["one_line_recall"])
    if not scene.strip() or not recall.strip():
        raise StructuredOutputError("mnemonic scene and recall line are required")
    return MnemonicResult(scene, associations, recall)


def validate_adjudication(data: dict[str, Any], option_ids: tuple[str, ...]) -> AdjudicationResult:
    _required(data, {"final_predicted_option", "decision", "confidence", "unresolved_ambiguity"})
    option = data["final_predicted_option"]
    if option is not None: option = _option(option, option_ids)
    if bool(data["unresolved_ambiguity"]) and option is not None:
        raise StructuredOutputError("unresolved adjudication must not force an option")
    return AdjudicationResult(option, str(data["decision"]), _confidence(data["confidence"]), bool(data["unresolved_ambiguity"]))


def _task_prompt(task: str) -> str:
    instructions = {
        "resolver": "Resolve independently. Inspect every option, image, numerical datum, scale, clinical clue, and polarity word such as MÁS, MENOS, INCORRECTA, EXCEPTO, FALSA or PRIMERA. Return only JSON with prediction, confidence, clues and concise reasoning. This is predicted, never official.",
        "reviewer": "Resolve independently without seeing another answer. Check multiple plausible answers and possible invalidity. Never claim official annulment.",
        "clinical": "Return JSON clinical reasoning without duplicating the resolver.",
        "pharmacology": "Return JSON with applies=false and no filler when pharmacology is irrelevant.",
        "concepts": "Return JSON terminology plus concise scales, values and formulas with intuitive MIR interpretation.",
        "options": "Return JSON analysis for every option, including verdict, evidence, alternate scenario and genuine MIR trap only.",
        "high_yield": "Return JSON with 3-7 reusable MIR high-yield points.",
        "mnemonic": "Return JSON for a vivid absurd scene and explicit visual_element to accepted medical_fact mappings. Add no new facts and imitate no author.",
        "adjudicator": "Adjudicate disagreement. Return JSON and leave option null if ambiguity remains.",
    }
    return f"TASK={task}\n{instructions[task]}"


def _render_package(package: QuestionPackage, context: dict[str, Any]) -> str:
    option_ids = [item["option_id"] for item in package.options]
    payload = {
        "question_number": package.question_number, "stem": package.stem,
        "options": package.options, "has_image_reference": package.has_image_reference,
        "referenced_image_number": package.referenced_image_number,
        "context": {key: asdict(value) if hasattr(value, "__dataclass_fields__") else value for key, value in context.items()},
    }
    return f"OPTION_IDS_JSON={json.dumps(option_ids)}\n{json.dumps(payload, ensure_ascii=False)}"


def _question_summary(package: QuestionPackage) -> dict[str, Any]:
    return {"stem": package.stem, "options": package.options, "image": {"required": package.has_image_reference, "asset_id": package.images[0].asset_id if package.images else None, "referenced_image_number": package.referenced_image_number}}


def _trace(name: str, provider: str, model: str, start: float, status: str, error: str | None = None) -> AgentTrace:
    return AgentTrace(name, provider, model, status, max(0, round((time.perf_counter() - start) * 1000)), error)
