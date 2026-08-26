import random

import pytest

from src.modules.revisions.schemas import RandomRevisionSessionRequest
from src.modules.revisions.selection import QuestionCandidate
from src.modules.revisions.service import (
    InsufficientQuestionBankError,
    RevisionSessionService,
)


class FakeSession:
    def __init__(self, fail_commit: bool = False) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.fail_commit = fail_commit

    def commit(self) -> None:
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError("synthetic commit failure")

    def rollback(self) -> None:
        self.rollbacks += 1


def test_shortage_rolls_back_and_never_commits(monkeypatch) -> None:
    from src.modules.revisions import repository

    db = FakeSession()
    monkeypatch.setattr(
        repository,
        "list_owned_eligible_candidates",
        lambda _db, _user_id: [QuestionCandidate(1)],
    )

    service = RevisionSessionService(db, random.Random(1))  # type: ignore[arg-type]
    with pytest.raises(InsufficientQuestionBankError):
        service.create(
            7,
            RandomRevisionSessionRequest(
                quiz_type="RANDOM",
                question_count=2,
                allow_ai_generation=True,
            ),
        )

    assert db.commits == 0
    assert db.rollbacks == 1


def test_commit_failure_rolls_back(monkeypatch) -> None:
    db = FakeSession(fail_commit=True)
    service = RevisionSessionService(db)  # type: ignore[arg-type]
    monkeypatch.setattr(service, "_create_random", lambda *_args: object())

    with pytest.raises(RuntimeError, match="synthetic commit failure"):
        service.create(
            7,
            RandomRevisionSessionRequest(
                quiz_type="RANDOM",
                question_count=1,
            ),
        )

    assert db.commits == 1
    assert db.rollbacks == 1
