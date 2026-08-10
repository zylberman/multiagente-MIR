import tempfile
import unittest
from pathlib import Path

from mir_multiagent.ingestion import (
    SourceSpan,
    _extract_image_assets,
    parse_questions,
    parse_questions_with_report,
)
from mir_multiagent.models import MirQuestion, QuestionAsset


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
        self.assertIn("associated image not found", questions[1].warnings)

    def test_duplicate_option_block_does_not_hide_following_question(self) -> None:
        text = """1. Malformed synthetic question
1. Alpha
2. Beta
2. Duplicate beta
3. Gamma
4. Delta

2. Valid following question
1. One
2. Two
3. Three
4. Four
"""
        result = parse_questions_with_report(text)
        self.assertEqual([question.question_id for question in result.questions], ["2"])
        self.assertGreaterEqual(result.discarded_questions, 1)
        self.assertTrue(any(issue.code == "UNRECOGNIZED_LAYOUT" for issue in result.issues))

    def test_number_inside_stem_is_not_an_option_marker(self) -> None:
        text = """10. Synthetic patient has 2 findings in prose.
1. Alpha
2. Beta
3. Gamma
4. Delta
"""
        question = parse_questions(text)[0]
        self.assertEqual(question.question_id, "10")
        self.assertIn("2 findings", question.stem)

    def test_five_numeric_options(self) -> None:
        text = """20. Numeric five-option question
1. One
2. Two
3. Three
4. Four
5. Five
"""
        self.assertEqual(len(parse_questions(text)[0].options), 5)

    def test_five_alphabetic_options(self) -> None:
        text = """21. Alphabetic five-option question
A. One
B. Two
C. Three
D. Four
E. Five
"""
        self.assertEqual([option.option_id for option in parse_questions(text)[0].options], list("ABCDE"))

    def test_question_asset_is_associated_through_canonical_contract(self) -> None:
        asset = QuestionAsset(
            asset_id="synthetic-p1-img1",
            source_page=1,
            source_image_number=1,
            local_path="data/images/synthetic.png",
        )
        question = parse_questions(
            "1. Pregunta vinculada a la imagen nº 1\n1. A\n2. B\n3. C\n4. D\n",
            source_page=1,
            assets=(asset,),
        )[0]
        self.assertEqual(len(question.assets), 1)
        self.assertEqual(question.assets[0].asset_id, asset.asset_id)
        self.assertEqual(question.referenced_image_number, 1)
        self.assertEqual(question.assets[0].association_confidence, 1.0)

    def test_unnumbered_image_reference_remains_separate_without_unique_asset(self) -> None:
        assets = tuple(
            QuestionAsset(asset_id=f"a-{number}", source_page=1, source_image_number=number,
                          local_path=f"image-{number}.png")
            for number in (1, 2)
        )
        question = parse_questions(
            "1. Véase imagen y seleccione\n1. A\n2. B\n3. C\n4. D\n",
            source_page=1,
            assets=assets,
        )[0]
        self.assertTrue(question.has_associated_image)
        self.assertIsNone(question.referenced_image_number)
        self.assertEqual(question.assets, ())

    def test_question_continued_across_page_preserves_provenance(self) -> None:
        page_one = "1. Cross-page synthetic question"
        page_two = "1. A\n2. B\n3. C\n4. D"
        text = page_one + "\n" + page_two
        spans = (
            SourceSpan(0, len(page_one), 1, "right"),
            SourceSpan(len(page_one) + 1, len(text), 2, "left"),
        )
        question = parse_questions_with_report(text, source_spans=spans).questions[0]
        self.assertEqual(question.source_pages, (1, 2))
        self.assertIn("QUESTION_CONTINUED_ACROSS_PAGE", question.warnings)

    def test_question_continued_across_columns_preserves_column(self) -> None:
        left = "1. Cross-column synthetic question"
        right = "1. A\n2. B\n3. C\n4. D"
        text = left + "\n" + right
        spans = (
            SourceSpan(0, len(left), 1, "left"),
            SourceSpan(len(left) + 1, len(text), 1, "right"),
        )
        question = parse_questions_with_report(text, source_spans=spans).questions[0]
        self.assertEqual(question.source_column, "left")
        self.assertEqual(question.source_pages, (1,))

    def test_embedded_image_extraction_writes_asset(self) -> None:
        class RenderedImage:
            def save(self, path: Path, format: str) -> None:
                path.write_bytes(b"synthetic-image")

        class CroppedPage:
            def to_image(self, resolution: int) -> RenderedImage:
                return RenderedImage()

        class Page:
            images = [{"x0": 0, "top": 0, "x1": 10, "bottom": 10}]

            def crop(self, bbox: tuple[int, int, int, int]) -> CroppedPage:
                return CroppedPage()

        with tempfile.TemporaryDirectory() as directory:
            issues = []
            assets = _extract_image_assets([Page()], Path("synthetic.pdf"), Path(directory), issues)
            self.assertEqual(len(assets), 1)
            self.assertTrue(Path(assets[0].local_path).is_file())
            self.assertEqual(assets[0].source_image_number, 1)
            self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
