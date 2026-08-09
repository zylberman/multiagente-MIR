import unittest

from mir_multiagent.ingestion import parse_questions
from mir_multiagent.models import MirQuestion


SYNTHETIC_TEXT = """1. Paciente ficticio para una prueba sintética. ¿Qué opción elegiría?
1. Opción alfa
2. Opción beta
3. Opción gamma
4. Opción delta

2. Pregunta vinculada a la imagen nº 1. Seleccione una opción.
A. Hallazgo uno
B. Hallazgo dos
C. Hallazgo tres
D. Hallazgo cuatro
"""


class IngestionTests(unittest.TestCase):
    def test_parser_returns_structured_questions(self) -> None:
        questions = parse_questions(SYNTHETIC_TEXT, source_pdf="/private/source.pdf", source_page=1)
        self.assertEqual(len(questions), 2)
        self.assertTrue(all(isinstance(question, MirQuestion) for question in questions))
        self.assertEqual(questions[0].source_pdf, "source.pdf")
        self.assertTrue(questions[1].has_associated_image)
        self.assertIn("associated image not found", questions[1].metadata["warnings"])


if __name__ == "__main__":
    unittest.main()
