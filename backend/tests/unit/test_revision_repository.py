from types import SimpleNamespace

from src.modules.revisions.models import Question
from src.modules.revisions.repository import add_generated_content
from src.modules.revisions.schemas import GeneratedRevisionResponse


class RecordingSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)


def test_add_generated_content_persists_generated_questions() -> None:
    db = RecordingSession()
    item = SimpleNamespace(id=7, theory=None)
    content = GeneratedRevisionResponse.model_validate(
        {
            "theory": "Theory",
            "key_points": ["One", "Two"],
            "questions": [
                {
                    "question": "Question?",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "1",
                    "explanation": "B is correct",
                    "expected_time": 30,
                    "difficulty_level": 2,
                }
            ],
        }
    )

    add_generated_content(db, item, content)  # type: ignore[arg-type]

    questions = [entry for entry in db.added if isinstance(entry, Question)]
    assert item.theory == "Theory"
    assert len(questions) == 1
    assert questions[0].learning_item_id == 7
    assert questions[0].correct_option == "1"
