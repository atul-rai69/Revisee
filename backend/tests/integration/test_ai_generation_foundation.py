import json

import pytest
from sqlalchemy import inspect, select

from src.core.config import get_settings
from src.core.exceptions import ApplicationError
from src.integrations.ai.base import (
    AIOperation,
    AIUsage,
    StructuredAIResult,
)
from src.modules.ai_generation.models import AIGenerationCall, AIGenerationEvent
from src.modules.auth.models import User
from src.modules.learning_items.models import LearningItem
from src.modules.revisions import repository as question_repository
from src.modules.revisions.generation.fingerprint import question_fingerprint
from src.modules.revisions.generation.service import QuestionGenerationService
from src.modules.revisions.models import Question


class StructuredFakeProvider:
    def generate(self, _prompt: str) -> str:
        raise AssertionError("legacy generation must not be used")

    def generate_structured(self, _request) -> StructuredAIResult:
        return StructuredAIResult(
            text=json.dumps(
                {
                    "questions": [
                        {
                            "question": "Generated question?",
                            "options": ["A", "B", "C", "D"],
                            "correct_answer": "0",
                            "difficulty_level": 1,
                            "expected_time_seconds": 20,
                            "explanation": "Generated explanation",
                        }
                    ]
                }
            ),
            provider="fake",
            model="fake-model",
            response_id="fake-response",
            usage=AIUsage(input_tokens=20, output_tokens=30, total_tokens=50),
        )


def _user(db_session, registered_user) -> User:
    return db_session.query(User).filter(User.username == "atul").one()


def _item(db_session, user: User, title: str = "Item") -> LearningItem:
    item = LearningItem(
        user_id=user.id,
        title=title,
        description_text="<p>Owned source material</p>",
    )
    db_session.add(item)
    db_session.flush()
    return item


def _event(db_session, user: User) -> AIGenerationEvent:
    event = AIGenerationEvent(
        user_id=user.id,
        operation_type=AIOperation.SESSION_SHORTAGE.value,
        prompt_template_version="question-only-v1",
        status="PENDING",
        requested_count=1,
    )
    db_session.add(event)
    db_session.flush()
    return event


def _question_values(item_id: int, event_id: int) -> dict[str, object]:
    options = ("A", "B", "C", "D")
    return {
        "learning_item_id": item_id,
        "question_text": "Unique question?",
        "option_a": options[0],
        "option_b": options[1],
        "option_c": options[2],
        "option_d": options[3],
        "correct_option": "0",
        "explanation": "Explanation",
        "difficulty": 1,
        "expected_time_seconds": 20,
        "source": "ai-question-v1",
        "content_fingerprint": question_fingerprint("Unique question?", options),
        "generation_event_id": event_id,
    }


def test_phase2a_migration_structure_is_present(db_session) -> None:
    inspector = inspect(db_session.get_bind())

    assert "ai_generation_events" in inspector.get_table_names()
    assert "ai_generation_calls" in inspector.get_table_names()
    question_columns = {
        column["name"] for column in inspector.get_columns("questions")
    }
    assert {"content_fingerprint", "generation_event_id"} <= question_columns
    fingerprint_index = next(
        index
        for index in inspector.get_indexes("questions")
        if index["name"] == "uq_questions_learning_item_fingerprint"
    )
    assert fingerprint_index["unique"] is True
    assert "content_fingerprint" in str(
        fingerprint_index.get("dialect_options", {}).get("postgresql_where")
    )


def test_partial_unique_index_makes_insertion_conflict_safe(
    db_session,
    registered_user,
) -> None:
    user = _user(db_session, registered_user)
    item = _item(db_session, user)
    event = _event(db_session, user)
    values = _question_values(item.id, event.id)

    first = question_repository.insert_generated_questions_conflict_safe(
        db_session, [values]
    )
    second = question_repository.insert_generated_questions_conflict_safe(
        db_session, [values]
    )

    assert len(first) == 1
    assert second == {}
    assert db_session.query(Question).filter_by(learning_item_id=item.id).count() == 1


def test_generation_foreign_keys_preserve_event_and_remove_calls_correctly(
    db_session,
    registered_user,
) -> None:
    user = _user(db_session, registered_user)
    item = _item(db_session, user)
    event = _event(db_session, user)
    call = AIGenerationCall(
        generation_event_id=event.id,
        learning_item_id=item.id,
        source_identifier="a" * 64,
        call_order=1,
        allocated_count=1,
        status="PENDING",
    )
    db_session.add(call)
    db_session.flush()
    call_id = call.id

    db_session.delete(item)
    db_session.flush()
    db_session.expire_all()
    assert db_session.get(AIGenerationCall, call_id).learning_item_id is None

    db_session.delete(db_session.get(AIGenerationEvent, event.id))
    db_session.flush()
    assert db_session.scalar(
        select(AIGenerationCall.id).where(AIGenerationCall.id == call_id)
    ) is None


def test_final_persistence_failure_rolls_back_questions_and_marks_event_failed(
    db_session,
    registered_user,
    monkeypatch,
) -> None:
    user = _user(db_session, registered_user)
    item = _item(db_session, user)
    db_session.commit()

    def fail_insert(*_args, **_kwargs):
        raise RuntimeError("synthetic persistence failure")

    monkeypatch.setattr(
        question_repository,
        "insert_generated_questions_conflict_safe",
        fail_insert,
    )
    service = QuestionGenerationService(
        db_session,
        StructuredFakeProvider(),
        get_settings(),
    )

    with pytest.raises(ApplicationError, match="could not be saved"):
        service.generate_for_owned_item(
            user_id=user.id,
            learning_item_id=item.id,
            question_count=1,
            operation=AIOperation.SESSION_SHORTAGE,
        )

    assert db_session.query(Question).filter_by(learning_item_id=item.id).count() == 0
    event = db_session.query(AIGenerationEvent).one()
    assert event.status == "FAILED"
    assert event.safe_error_code == "AI_PERSISTENCE_FAILURE"
