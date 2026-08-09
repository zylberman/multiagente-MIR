"""Traceable P0 multi-agent routing and final assembly."""

from __future__ import annotations

from dataclasses import dataclass

from .agents import SpecializedAgent
from .config import AGENT_NAMES, Settings
from .models import AgentResult, FinalExplanation, MirQuestion
from .prompts import load_prompts
from .providers import LlmProvider


@dataclass
class MultiAgentPipeline:
    settings: Settings
    provider: LlmProvider
    prompts: dict[str, str]

    @classmethod
    def create(cls, settings: Settings, provider: LlmProvider) -> "MultiAgentPipeline":
        return cls(settings=settings, provider=provider, prompts=load_prompts())

    def run(self, question: MirQuestion) -> FinalExplanation:
        results: list[AgentResult] = []
        for name in AGENT_NAMES[:-1]:
            agent = SpecializedAgent(
                name=name,
                prompt=self.prompts[name],
                model=self.settings.agent_models[name],
                provider=self.provider,
            )
            results.append(agent.run(question, tuple(results)))

        mnemonic = SpecializedAgent(
            name="mnemonic",
            prompt=self.prompts["mnemonic"],
            model=self.settings.agent_models["mnemonic"],
            provider=self.provider,
        ).run(question, tuple(results))
        results.append(mnemonic)
        return assemble_final_explanation(question, tuple(results))


def assemble_final_explanation(
    question: MirQuestion, results: tuple[AgentResult, ...]
) -> FinalExplanation:
    by_name = {result.agent_name: result for result in results}
    required = {"answer", "pharmacology", "clinical", "terminology", "mnemonic"}
    missing = required - by_name.keys()
    if missing:
        raise ValueError(f"Missing agent results: {', '.join(sorted(missing))}")

    answer = by_name["answer"]
    extraction_warnings = question.warnings
    agent_warnings = tuple(warning for result in results for warning in result.warnings)
    evidence = tuple(note for result in results for note in result.evidence_notes)
    return FinalExplanation(
        question_id=question.question_id,
        predicted_correct_option=answer.predicted_option,
        final_answer_text=answer.content,
        clinical_explanation=by_name["clinical"].content,
        pharmacology_explanation=by_name["pharmacology"].content,
        terminology_explanation=by_name["terminology"].content,
        incorrect_option_analysis={},
        mnemonic_visual_analogy=by_name["mnemonic"].content,
        confidence=answer.confidence,
        evidence_notes=evidence,
        warnings=extraction_warnings + agent_warnings,
        agent_results=results,
    )
