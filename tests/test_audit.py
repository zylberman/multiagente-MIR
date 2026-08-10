import unittest

from mir_multiagent.audit import reconcile_images, reconcile_questions
from mir_multiagent.ingestion import IngestionResult
from mir_multiagent.models import MirQuestion, QuestionAsset, QuestionOption


def question(number: int | None, *, image: bool = False, assets: tuple[QuestionAsset, ...] = ()) -> MirQuestion:
    return MirQuestion(
        question_id=str(number) if number is not None else "internal-1",
        source_question_number=number,
        stem="Synthetic question",
        options=tuple(QuestionOption(str(index), f"Option {index}") for index in range(1, 5)),
        has_associated_image=image,
        assets=assets,
        warnings=("associated image not found",) if image and not assets else (),
    )


class QuestionReconciliationTests(unittest.TestCase):
    def test_consecutive_exam_is_complete(self) -> None:
        report = reconcile_questions([question(number) for number in range(1, 6)], 5)
        self.assertEqual(report.integrity_status, "complete")

    def test_missing_question_is_incomplete_without_filling_gap(self) -> None:
        questions = [question(1), question(3)]
        report = reconcile_questions(questions, 3)
        self.assertEqual(report.missing_question_numbers, (2,))
        self.assertEqual(len(questions), 2)
        self.assertEqual(report.integrity_status, "incomplete")

    def test_duplicate_question_is_suspicious(self) -> None:
        report = reconcile_questions([question(1), question(1), question(2)], 2)
        self.assertEqual(report.duplicate_question_numbers, (1,))
        self.assertEqual(report.integrity_status, "suspicious")

    def test_out_of_range_question_is_suspicious(self) -> None:
        report = reconcile_questions([question(1), question(4)], 3)
        self.assertEqual(report.unexpected_question_numbers, (4,))
        self.assertEqual(report.integrity_status, "suspicious")

    def test_question_without_number_is_reported(self) -> None:
        report = reconcile_questions([question(None)], 1)
        self.assertEqual(report.questions_without_source_number, ("internal-1",))
        self.assertEqual(report.integrity_status, "incomplete")

    def test_expected_210_never_creates_questions(self) -> None:
        questions = [question(number) for number in range(1, 4)]
        report = reconcile_questions(questions, 210)
        self.assertEqual(report.recovered_questions, 3)
        self.assertEqual(len(report.missing_question_numbers), 207)


class ImageReconciliationTests(unittest.TestCase):
    def test_image_entities_are_counted_separately(self) -> None:
        associated = QuestionAsset(
            asset_id="asset-1", source_image_number=1, source_page=5,
            local_path="asset-1.png", association_confidence=1.0,
        )
        unassociated = QuestionAsset(
            asset_id="asset-2", source_image_number=2, source_page=5,
            local_path="asset-2.png",
        )
        ingestion = IngestionResult(
            questions=[question(1, image=True, assets=(associated,)), question(2, image=True)],
            assets=[associated, unassociated],
        )
        report = reconcile_images(ingestion)
        self.assertEqual(report.images_extracted, 2)
        self.assertEqual(report.questions_referencing_images, 2)
        self.assertEqual(report.questions_with_assets, 1)
        self.assertEqual(report.high_confidence_associations, 1)
        self.assertEqual(report.image_questions_without_asset, (2,))
        self.assertEqual(report.unassociated_assets, ("asset-2",))
        self.assertIn("IMAGE_COUNT_OUTSIDE_EXPECTED_RANGE", report.warnings)

    def test_low_confidence_association_is_counted_separately(self) -> None:
        asset = QuestionAsset(
            asset_id="asset-low", source_page=1, local_path="asset-low.png",
            association_confidence=0.4,
        )
        ingestion = IngestionResult(
            questions=[question(1, image=True, assets=(asset,))], assets=[asset]
        )
        report = reconcile_images(ingestion)
        self.assertEqual(report.high_confidence_associations, 0)
        self.assertEqual(report.low_confidence_associations, 1)


if __name__ == "__main__":
    unittest.main()
