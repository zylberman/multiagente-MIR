"""Explicit specialized agents for the P0 sequential workflow."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .models import AgentResult, MirQuestion
from .providers import LlmProvider

LOGGER = logging.getLogger(__name__)


def render_question(question: MirQuestion) -> str:
    options = "\n".join(f"{item.option_id}. {item.text}" for item in question.options)
    image_note = (
        f"\nAssociated local images: {', '.join(question.associated_image_paths)}"
        if question.associated_image_paths
        else ""
    )
    return f"Question {question.question_id}: {question.stem}\n{options}{image_note}"


@dataclass(frozen=True)
class SpecializedAgent:
    name: str
    prompt: str
    model: str
    provider: LlmProvider

    def run(self, question: MirQuestion, context: tuple[AgentResult, ...] = ()) -> AgentResult:
        prior = "\n\n".join(f"[{item.agent_name}]\n{item.content}" for item in context)
        user_prompt = render_question(question)
        if prior:
            user_prompt += f"\n\nPrevious specialist analyses:\n{prior}"
        try:
            content = self.provider.complete(
                system_prompt=self.prompt,
                user_prompt=user_prompt,
                model=self.model,
            )
        except Exception as exc:
            LOGGER.error("Agent %s failed: %s", self.name, type(exc).__name__)
            return AgentResult(
                agent_name=self.name,
                content=f"Agent unavailable: {type(exc).__name__}",
                warnings=(f"{self.name} agent failed",),
            )
        return AgentResult(agent_name=self.name, content=content)
