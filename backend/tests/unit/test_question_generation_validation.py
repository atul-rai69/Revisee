import json

import pytest
from pydantic import ValidationError

from src.core.exceptions import ProviderOutputError
from src.modules.revisions.generation.schemas import (
    ValidatedGeneratedQuestion,
    parse_question_response,
)


def _question(**overrides):
    value = {
        "question": "What is a cell?",
        "options": ["Unit A", "Unit B", "Unit C", "Unit D"],
        "correct_answer": "0",
        "difficulty_level": 1,
        "expected_time_seconds": 20,
        "explanation": "A cell is the basic unit.",
    }
    value.update(overrides)
    return value


def test_entries_are_validated_independently_and_excess_is_counted() -> None:
    raw = json.dumps(
        {
            "questions": [
                _question(correct_answer="B"),
                _question(options=["A", "B"]),
                _question(question="Ignored excess"),
            ]
        }
    )
    parsed = parse_question_response(
        raw,
        requested_count=2,
        maximum_response_characters=10_000,
        maximum_expected_time_seconds=300,
    )

    assert len(parsed.questions) == 1
    assert parsed.questions[0].correct_answer == "1"
    assert parsed.rejected_count == 1
    assert parsed.excess_count == 1


@pytest.mark.parametrize("answer, expected", [(0, "0"), ("3", "3"), ("D", "3")])
def test_answer_forms_are_normalized(answer, expected: str) -> None:
    question = ValidatedGeneratedQuestion.model_validate(
        _question(correct_answer=answer),
        context={"maximum_expected_time_seconds": 60},
    )
    assert question.correct_answer == expected


@pytest.mark.parametrize(
    "overrides",
    [
        {"options": ["A", "B", "C"]},
        {"options": ["A", "B", "C", " "]},
        {"options": ["A", "B", "C", "a"]},
        {"correct_answer": "E"},
        {"difficulty_level": 0},
        {"difficulty_level": 4},
        {"expected_time_seconds": 0},
        {"expected_time_seconds": 61},
        {"question": " "},
        {"explanation": " "},
        {"unexpected": "field"},
    ],
)
def test_invalid_question_fields_are_rejected(overrides) -> None:
    with pytest.raises(ValidationError):
        ValidatedGeneratedQuestion.model_validate(
            _question(**overrides),
            context={"maximum_expected_time_seconds": 60},
        )


def test_response_size_is_bounded_before_json_parsing() -> None:
    with pytest.raises(ProviderOutputError, match="invalid data"):
        parse_question_response(
            "x" * 101,
            requested_count=1,
            maximum_response_characters=100,
            maximum_expected_time_seconds=60,
        )


@pytest.mark.parametrize(
    "value",
    ["not json", "[]", '{"questions": {}}', '{"questions": [], "raw": true}'],
)
def test_invalid_top_level_output_is_sanitized(value: str) -> None:
    with pytest.raises(ProviderOutputError) as error:
        parse_question_response(
            value,
            requested_count=1,
            maximum_response_characters=1_000,
            maximum_expected_time_seconds=60,
        )
    assert value not in str(error.value)
