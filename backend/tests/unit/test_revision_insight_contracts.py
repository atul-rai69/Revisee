from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.modules.learning_items.schemas import ManualQuestionCreateRequest
from src.modules.mastery import repository as mastery_repository
from src.modules.mastery.repository import MasteryAnalyticsRow
from src.modules.mastery.service import MasteryAnalyticsService
from src.modules.revisions import repository as revision_repository
from src.modules.revisions.service import RevisionSessionService


class FakeDb:
    def __init__(self) -> None:
        self.rollbacks = 0

    def rollback(self) -> None:
        self.rollbacks += 1


def test_manual_question_validation_trims_and_rejects_duplicate_options() -> None:
    request = ManualQuestionCreateRequest(
        question="  Question?  ", option_a=" A ", option_b="B", option_c="C",
        option_d="D", correct_option="A", explanation="  Because. ",
        difficulty=2, expected_time_seconds=30,
    )
    assert request.question == "Question?"
    assert request.option_a == "A"
    with pytest.raises(ValidationError):
        ManualQuestionCreateRequest(
            question="Question?", option_a="Same", option_b="same", option_c="C",
            option_d="D", correct_option="A", explanation="Because.",
            difficulty=2, expected_time_seconds=30,
        )


def test_unattempted_mastery_hides_database_default(monkeypatch) -> None:
    row = MasteryAnalyticsRow(
        entity_id=1, display_name="Unattempted", question_count=2,
        mastery_score=Decimal("50.00"), total_attempts=0, correct_attempts=0,
        last_attempted_at=None, next_review_at=None,
    )
    monkeypatch.setattr(mastery_repository, "list_owned_mastery_analytics", lambda *_args, **_kwargs: ([row], 1))
    monkeypatch.setattr(mastery_repository, "list_mastery_history", lambda *_args, **_kwargs: {})
    response = MasteryAnalyticsService(FakeDb()).list(1, entity_type="LEARNING_ITEM", limit=20, offset=0)
    assert response.items[0].evidence_status == "NOT_ATTEMPTED"
    assert response.items[0].mastery_score is None
    assert response.items[0].accuracy_percent is None


def test_insufficient_evidence_hides_current_mastery(monkeypatch) -> None:
    row = MasteryAnalyticsRow(
        entity_id=2, display_name="Early evidence", question_count=2,
        mastery_score=Decimal("56.00"), total_attempts=2, correct_attempts=1,
        last_attempted_at=datetime(2026, 9, 14), next_review_at=None,
    )
    monkeypatch.setattr(mastery_repository, "list_owned_mastery_analytics", lambda *_args, **_kwargs: ([row], 1))
    monkeypatch.setattr(mastery_repository, "list_mastery_history", lambda *_args, **_kwargs: {})
    response = MasteryAnalyticsService(FakeDb()).list(1, entity_type="LABEL", limit=20, offset=0)
    assert response.items[0].evidence_status == "INSUFFICIENT_EVIDENCE"
    assert response.items[0].mastery_score is None
    assert response.items[0].accuracy_percent == 50


def test_history_never_assigns_scores_to_active_sessions(monkeypatch) -> None:
    active = SimpleNamespace(
        id=3, status="IN_PROGRESS", requested_strategy="RANDOM",
        strategy_used="RANDOM", started_at=datetime(2026, 9, 14), ended_at=None,
        requested_question_count=5,
    )
    monkeypatch.setattr(revision_repository, "list_owned_sessions", lambda *_args, **_kwargs: [active])
    monkeypatch.setattr(revision_repository, "list_labels_for_sessions", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(revision_repository, "summarize_attempts_for_sessions", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(revision_repository, "count_owned_sessions", lambda *_args, **_kwargs: 1)
    response = RevisionSessionService(FakeDb()).history(1, status=None, limit=10, offset=0)
    assert response.items[0].correct_count is None
    assert response.items[0].score_percentage is None
    assert response.items[0].total_time_taken_seconds is None
