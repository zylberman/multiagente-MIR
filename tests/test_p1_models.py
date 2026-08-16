import tempfile
import unittest
from pathlib import Path

from mir_multiagent.models import MirQuestion, QuestionAsset, QuestionOption
from mir_multiagent.p1_models import build_question_package


def question(*, image: bool = False, assets: tuple[QuestionAsset, ...] = ()) -> MirQuestion:
    return MirQuestion(
        question_id="7", source_question_number=7, stem="Synthetic P1 question",
        options=tuple(QuestionOption(str(i), f"Option {i}") for i in range(1, 5)),
        has_associated_image=image, assets=assets,
        warnings=("associated image not found",) if image and not assets else (),
    )


class QuestionPackageTests(unittest.TestCase):
    def test_text_only_package_has_no_images(self) -> None:
        gate = build_question_package(question())
        self.assertEqual(gate.status, "complete")
        self.assertEqual(gate.package.images, ())

    def test_image_package_contains_actual_bytes_not_only_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image.png"
            path.write_bytes(b"real-synthetic-image-bytes")
            asset = QuestionAsset(
                "asset-7", source_image_number=7, local_path=str(path),
                association_confidence=1.0,
            )
            gate = build_question_package(question(image=True, assets=(asset,)))
        self.assertEqual(gate.status, "complete")
        self.assertEqual(gate.package.images[0].content, b"real-synthetic-image-bytes")

    def test_missing_required_image_is_blocked(self) -> None:
        gate = build_question_package(question(image=True))
        self.assertEqual(gate.status, "missing_required_image")
        self.assertIsNone(gate.package)

    def test_missing_asset_file_is_blocked(self) -> None:
        asset = QuestionAsset(
            "missing", local_path="/definitely/not/a/real/image.png",
            association_confidence=1.0,
        )
        gate = build_question_package(question(image=True, assets=(asset,)))
        self.assertEqual(gate.status, "missing_required_image")

    def test_low_confidence_asset_needs_review(self) -> None:
        asset = QuestionAsset("low", local_path="unused.png", association_confidence=0.4)
        gate = build_question_package(question(image=True, assets=(asset,)))
        self.assertEqual(gate.status, "needs_asset_review")


if __name__ == "__main__":
    unittest.main()
