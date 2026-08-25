import json

import pytest

from src.core.exceptions import ProviderOutputError
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
