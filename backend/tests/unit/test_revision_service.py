import json

import pytest

from src.core.exceptions import ProviderOutputError
from src.modules.revisions.generation.preferences import GenerationPreferences
from src.modules.revisions.service import RevisionService


class StubProvider:
    def __init__(self, value: str) -> None:
        self.value = value

    def generate(self, _prompt: str) -> str:
        return self.value


def valid_revision() -> dict[str, object]:
    return {
        "theory": "Theory",
        "key_points": ["Point"],
        "questions": [
            {
                "question": "Question?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": 2,
                "explanation": "Explanation",
                "expected_time": 10,
                "difficulty_level": 1,
            }
        ],
    }


def test_generation_normalizes_correct_answer() -> None:
    service = RevisionService(None, StubProvider(json.dumps(valid_revision())))  # type: ignore[arg-type]
    content = service.generate_content("Title", "Description")
    assert content.questions[0].correct_answer == "2"


def test_selected_full_content_sections_remove_unrequested_output() -> None:
    service = RevisionService(None, StubProvider(json.dumps(valid_revision())))  # type: ignore[arg-type]
    content = service.generate_content(
        "Title",
        "Description",
        preferences=GenerationPreferences(content_sections=["THEORY"]),
    )
    assert content.theory == "Theory"
    assert content.key_points == []
    assert content.questions == []


def test_explicit_question_type_and_difficulty_override_defaults() -> None:
    generated = valid_revision()
    generated["questions"] = [
        {
            **valid_revision()["questions"][0],  # type: ignore[index]
            "question_type": "CODING",
            "difficulty_level": 3,
        },
        {
            **valid_revision()["questions"][0],  # type: ignore[index]
            "question": "Wrong type?",
            "question_type": "THEORY",
            "difficulty_level": 3,
        },
    ]
    service = RevisionService(None, StubProvider(json.dumps(generated)))  # type: ignore[arg-type]
    content = service.generate_content(
        "Title",
        "Description",
        preferences=GenerationPreferences(
            question_count=2,
            question_types=["CODING"],
            difficulty_mode="HARD",
            coding_preferences={
                "language": "PYTHON",
                "question_formats": ["DEBUGGING"],
            },
        ),
    )
    assert len(content.questions) == 1
    assert content.questions[0].question_type == "CODING"
    assert content.questions[0].difficulty_level == 3


@pytest.mark.parametrize(
    "raw",
    [
        "not-json",
        json.dumps({}),
        json.dumps({**valid_revision(), "questions": []}),
        json.dumps(
            {
                **valid_revision(),
                "questions": [
                    {
                        **valid_revision()["questions"][0],  # type: ignore[index]
                        "options": ["A", "B"],
                    }
                ],
            }
        ),
    ],
)
def test_invalid_provider_output_is_rejected(raw: str) -> None:
    service = RevisionService(None, StubProvider(raw))  # type: ignore[arg-type]
    with pytest.raises(ProviderOutputError):
        service.generate_content("Title", "Description")
