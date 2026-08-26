import pytest
from pydantic import TypeAdapter, ValidationError

from src.modules.revisions.schemas import (
    LabelRevisionSessionRequest,
    RevisionSessionRequest,
    RevisionSessionResponse,
)


adapter = TypeAdapter(RevisionSessionRequest)


def test_random_rejects_label_fields() -> None:
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "quiz_type": "RANDOM",
                "question_count": 5,
                "label_ids": [1],
            }
        )


def test_label_rejects_question_count() -> None:
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "quiz_type": "LABEL",
                "label_ids": [1],
                "questions_per_label": 5,
                "question_count": 5,
            }
        )


def test_label_derives_total_and_rejects_duplicates() -> None:
    request = adapter.validate_python(
        {
            "quiz_type": "LABEL",
            "label_ids": [2, 5],
            "questions_per_label": 5,
        }
    )
    assert isinstance(request, LabelRevisionSessionRequest)
    assert request.question_count == 10

    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "quiz_type": "LABEL",
                "label_ids": [2, 2],
                "questions_per_label": 2,
            }
        )


def test_label_rejects_derived_total_above_fifty() -> None:
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "quiz_type": "LABEL",
                "label_ids": [1, 2, 3],
                "questions_per_label": 20,
            }
        )


@pytest.mark.parametrize("questions_per_label", [0, 21])
def test_label_rejects_out_of_range_quota(questions_per_label: int) -> None:
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "quiz_type": "LABEL",
                "label_ids": [1],
                "questions_per_label": questions_per_label,
            }
        )


def test_label_rejects_nonpositive_label_id() -> None:
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "quiz_type": "LABEL",
                "label_ids": [0],
                "questions_per_label": 1,
            }
        )


def test_pre_submission_schema_has_no_answer_fields() -> None:
    question_properties = RevisionSessionResponse.model_json_schema()["$defs"][
        "RevisionSessionQuestionResponse"
    ]["properties"]
    assert "correct_option" not in question_properties
    assert "explanation" not in question_properties
    assert "question_id" not in question_properties
    assert "source" not in question_properties
    assert "session_question_id" in question_properties
