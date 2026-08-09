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
            AgentResult(agent_name=name, content=f"{name} output")
            for name in ("answer", "pharmacology", "clinical", "terminology", "mnemonic")
        )
        final = assemble_final_explanation(question, results)
        self.assertEqual(final.question_id, "7")
        self.assertEqual(final.clinical_explanation, "clinical output")
        self.assertEqual(final.mnemonic_visual_analogy, "mnemonic output")
        self.assertEqual(len(final.agent_results), 5)


if __name__ == "__main__":
    unittest.main()
