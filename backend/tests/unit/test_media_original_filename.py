from src.modules.learning_items.service import LearningItemService


def test_original_filename_removes_client_paths_and_control_characters() -> None:
    assert LearningItemService._safe_original_filename(
        "C:\\fakepath\\Biology\u202e\x00 Notes.pdf"
    ) == "Biology Notes.pdf"
    assert LearningItemService._safe_original_filename("../../Chemistry.pdf") == "Chemistry.pdf"


def test_original_filename_preserves_extension_within_database_limit() -> None:
    value = LearningItemService._safe_original_filename(f"{'a' * 300}.pdf")
    assert value is not None
    assert len(value) == 255
    assert value.endswith(".pdf")


def test_original_filename_rejects_empty_or_path_only_values() -> None:
    assert LearningItemService._safe_original_filename(None) is None
    assert LearningItemService._safe_original_filename("../..") is None
