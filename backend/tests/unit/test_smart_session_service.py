import random
from decimal import Decimal

import pytest

from src.modules.revisions.schemas import SmartRevisionSessionRequest
from src.modules.revisions.service import (
    InsufficientQuestionBankError,
    RevisionSessionService,
)
from src.modules.revisions.smart_selection import SmartQuestionCandidate


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def smart_candidate(
    question_id: int,
    item_id: int,
    *,
    score: str | None = None,
    attempts: int = 0,
) -> SmartQuestionCandidate:
    return SmartQuestionCandidate(
        question_id=question_id,
        learning_item_id=item_id,
        mastery_score=Decimal(score) if score else None,
        total_attempts=attempts,
        next_review_at=None,
    )


def test_smart_creation_reports_random_fallback_and_never_uses_provider(
    monkeypatch,
) -> None:
    from src.modules.revisions import repository

    db = FakeSession()
    service = RevisionSessionService(db, random.Random(4))  # type: ignore[arg-type]
    monkeypatch.setattr(
        repository,
        "list_owned_eligible_smart_candidates",
        lambda *_args: [smart_candidate(1, 1), smart_candidate(2, 2)],
    )
    persisted: dict[str, object] = {}

    def capture(**kwargs):
        persisted.update(kwargs)
        return "response"

    monkeypatch.setattr(service, "_persist_session", capture)
    result = service.create(
        9,
        SmartRevisionSessionRequest(
            quiz_type="SMART",
            question_count=2,
            allow_ai_generation=True,
        ),
    )

    assert result == "response"
    assert persisted["requested_strategy"] == "SMART"
    assert persisted["strategy_used"] == "RANDOM"
    assert persisted["allow_ai_generation"] is True
    assert db.commits == 1


def test_partial_personalization_reports_smart(monkeypatch) -> None:
    from src.modules.revisions import repository

    db = FakeSession()
    service = RevisionSessionService(db, random.Random(5))  # type: ignore[arg-type]
    monkeypatch.setattr(
        repository,
        "list_owned_eligible_smart_candidates",
        lambda *_args: [
            smart_candidate(1, 1, score="30", attempts=3),
            smart_candidate(2, 2),
        ],
    )
    persisted: dict[str, object] = {}
    monkeypatch.setattr(
        service,
        "_persist_session",
        lambda **kwargs: persisted.update(kwargs) or "response",
    )

    service.create(
        9,
        SmartRevisionSessionRequest(quiz_type="SMART", question_count=2),
    )
    assert persisted["strategy_used"] == "SMART"
    assert len(persisted["ordered_assignments"]) == 2


def test_smart_shortage_rolls_back_without_persistence(monkeypatch) -> None:
    from src.modules.revisions import repository

    db = FakeSession()
    service = RevisionSessionService(db)  # type: ignore[arg-type]
    monkeypatch.setattr(
        repository,
        "list_owned_eligible_smart_candidates",
        lambda *_args: [smart_candidate(1, 1)],
    )
    monkeypatch.setattr(
        service,
        "_persist_session",
        lambda **_kwargs: pytest.fail("shortage must not persist a session"),
    )

    with pytest.raises(InsufficientQuestionBankError) as caught:
        service.create(
            9,
            SmartRevisionSessionRequest(quiz_type="SMART", question_count=2),
        )

    assert caught.value.detail["assignable_question_count"] == 1
    assert caught.value.detail["total_shortage"] == 1
    assert db.commits == 0
    assert db.rollbacks == 1
