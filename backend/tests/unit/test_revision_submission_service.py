from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.core.exceptions import ApplicationError
from src.modules.revisions.models import RevisionSessionQuestion, UserAttempt
from src.modules.revisions.submission_schemas import RevisionSessionSubmitRequest
from src.modules.revisions.submission_service import (
    GradedAnswer,
    RevisionSubmissionError,
    RevisionSubmissionService,
    normalize_snapshot_answer,
)


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _session(status: str = "IN_PROGRESS"):
    return SimpleNamespace(
        id=5,
        user_id=7,
        status=status,
        requested_question_count=2,
        requested_strategy="RANDOM",
        strategy_used="RANDOM",
        started_at=datetime(2026, 8, 26, 9, 0, 0),
        ended_at=(datetime(2026, 8, 26, 10, 0, 0) if status == "COMPLETED" else None),
    )


def _question(question_id: int, order: int, correct: str) -> RevisionSessionQuestion:
    return RevisionSessionQuestion(
        id=question_id,
        session_id=5,
        question_id=None,
        learning_item_id=None,
        question_order=order,
        learning_item_title_snapshot="Item",
        question_text_snapshot=f"Question {order}?",
        option_a_snapshot="A",
        option_b_snapshot="B",
        option_c_snapshot="C",
        option_d_snapshot="D",
        correct_option_snapshot=correct,
        explanation_snapshot=f"Explanation {order}",
        difficulty_snapshot=2,
        expected_time_seconds_snapshot=30,
        source_snapshot="stored",
        generated_for_session=False,
    )


def _request(*ids: int) -> RevisionSessionSubmitRequest:
    return RevisionSessionSubmitRequest.model_validate(
        {
            "answers": [
                {
                    "session_question_id": question_id,
                    "selected_option": "B" if index == 0 else "A",
                    "time_taken_seconds": 20 + index,
                }
                for index, question_id in enumerate(ids)
            ]
        }
    )


def _install_successful_repository(monkeypatch, *, fail_attempts: bool = False):
    from src.modules.mastery import repository as mastery_repository
    from src.modules.revisions import submission_repository as repository

    session = _session()
    questions = [_question(12, 1, "1"), _question(11, 2, "A")]
    attempts: list[object] = []
    monkeypatch.setattr(repository, "find_owned_session_for_update", lambda *_: session)
    monkeypatch.setattr(repository, "list_session_questions", lambda *_: questions)
    monkeypatch.setattr(repository, "lock_owned_learning_items", lambda *_: {})
    monkeypatch.setattr(repository, "lock_owned_questions", lambda *_: {})
    monkeypatch.setattr(repository, "lock_current_labels_by_item", lambda *_: {})
    monkeypatch.setattr(repository, "list_session_labels", lambda *_: [])
    monkeypatch.setattr(repository, "upsert_question_statistics", lambda *_: None)
    monkeypatch.setattr(repository, "flush", lambda *_: None)

    def add_attempts(_db, values):
        if fail_attempts:
            raise RuntimeError("attempt insert failed")
        attempts.extend(values)

    monkeypatch.setattr(repository, "add_attempts", add_attempts)
    monkeypatch.setattr(mastery_repository, "materialize_item_mastery", lambda *_: None)
    monkeypatch.setattr(mastery_repository, "materialize_label_mastery", lambda *_: None)
    monkeypatch.setattr(mastery_repository, "lock_item_mastery", lambda *_: [])
    monkeypatch.setattr(mastery_repository, "lock_label_mastery", lambda *_: [])
    return session, questions, attempts


def test_snapshot_answer_normalization() -> None:
    assert [normalize_snapshot_answer(value) for value in ("0", "1", "2", "3")] == [
        "A",
        "B",
        "C",
        "D",
    ]
    assert normalize_snapshot_answer("b") == "B"
    with pytest.raises(RevisionSubmissionError) as exc_info:
        normalize_snapshot_answer("invalid")
    assert exc_info.value.code == "REVISION_SESSION_RESULT_UNAVAILABLE"


def test_mastery_attribution_uses_item_and_all_current_labels() -> None:
    first = _question(12, 1, "1")
    first.learning_item_id = 40
    second = _question(11, 2, "A")
    second.learning_item_id = 40
    graded = [
        GradedAnswer(first, _request(12).answers[0], "B", True, Decimal("7.50")),
        GradedAnswer(second, _request(11).answers[0], "A", False, Decimal("-6.00")),
    ]

    item_batches, label_batches = RevisionSubmissionService._mastery_batches(
        graded,
        {40},
        {40: (3, 9)},
    )

    assert item_batches[40].delta == Decimal("1.50")
    assert item_batches[40].attempt_count == 2
    assert label_batches[3] == item_batches[40]
    assert label_batches[9] == item_batches[40]


def test_submission_commits_once_and_returns_persisted_order(monkeypatch) -> None:
    db = FakeSession()
    session, _questions, attempts = _install_successful_repository(monkeypatch)

    result = RevisionSubmissionService(db).submit(7, 5, _request(12, 11))  # type: ignore[arg-type]

    assert db.commits == 1
    assert db.rollbacks == 0
    assert session.status == "COMPLETED"
    assert [question.session_question_id for question in result.questions] == [12, 11]
    assert [question.correct_option for question in result.questions] == ["B", "A"]
    assert [question.is_correct for question in result.questions] == [True, True]
    assert len(attempts) == 2


def test_answer_set_mismatch_rolls_back_without_commit(monkeypatch) -> None:
    db = FakeSession()
    _install_successful_repository(monkeypatch)

    with pytest.raises(RevisionSubmissionError) as exc_info:
        RevisionSubmissionService(db).submit(7, 5, _request(12))  # type: ignore[arg-type]

    assert exc_info.value.code == "ANSWER_SET_MISMATCH"
    assert db.commits == 0
    assert db.rollbacks == 1


def test_failed_persistence_rolls_back_everything(monkeypatch) -> None:
    db = FakeSession()
    session, _questions, _attempts = _install_successful_repository(
        monkeypatch,
        fail_attempts=True,
    )

    with pytest.raises(ApplicationError, match="Revision session submission failed"):
        RevisionSubmissionService(db).submit(7, 5, _request(12, 11))  # type: ignore[arg-type]

    assert db.commits == 0
    assert db.rollbacks == 1
    assert session.status == "IN_PROGRESS"


def test_repeated_submission_returns_stable_conflict(monkeypatch) -> None:
    from src.modules.revisions import submission_repository as repository

    db = FakeSession()
    monkeypatch.setattr(
        repository,
        "find_owned_session_for_update",
        lambda *_: _session("COMPLETED"),
    )
    with pytest.raises(RevisionSubmissionError) as exc_info:
        RevisionSubmissionService(db).submit(7, 5, _request(12, 11))  # type: ignore[arg-type]
    assert exc_info.value.code == "REVISION_SESSION_ALREADY_COMPLETED"
    assert exc_info.value.status_code == 409
    assert db.commits == 0
    assert db.rollbacks == 1


def test_corrupt_non_in_progress_state_is_rejected(monkeypatch) -> None:
    from src.modules.revisions import submission_repository as repository

    db = FakeSession()
    corrupt = _session()
    corrupt.status = "UNKNOWN"
    monkeypatch.setattr(
        repository,
        "find_owned_session_for_update",
        lambda *_: corrupt,
    )
    with pytest.raises(RevisionSubmissionError) as exc_info:
        RevisionSubmissionService(db).submit(7, 5, _request(12, 11))  # type: ignore[arg-type]
    assert exc_info.value.code == "REVISION_SESSION_RESULT_UNAVAILABLE"
    assert db.commits == 0
    assert db.rollbacks == 1


def test_result_before_completion_is_rejected(monkeypatch) -> None:
    from src.modules.revisions import submission_repository as repository

    db = FakeSession()
    monkeypatch.setattr(repository, "find_owned_session", lambda *_: _session())
    with pytest.raises(RevisionSubmissionError) as exc_info:
        RevisionSubmissionService(db).result(7, 5)  # type: ignore[arg-type]
    assert exc_info.value.code == "REVISION_SESSION_NOT_COMPLETED"


def test_corrupt_persisted_grading_is_not_returned() -> None:
    session = _session("COMPLETED")
    questions = [_question(12, 1, "1"), _question(11, 2, "A")]
    attempts = [
        UserAttempt(
            user_id=7,
            session_id=5,
            session_question_id=12,
            selected_option="B",
            is_correct=False,
            time_taken_seconds=15,
            mastery_delta=Decimal("7.50"),
            attempted_at=datetime(2026, 8, 26, 10, 0, 0),
        ),
        UserAttempt(
            user_id=7,
            session_id=5,
            session_question_id=11,
            selected_option="A",
            is_correct=True,
            time_taken_seconds=15,
            mastery_delta=Decimal("7.50"),
            attempted_at=datetime(2026, 8, 26, 10, 0, 0),
        ),
    ]

    with pytest.raises(RevisionSubmissionError) as exc_info:
        RevisionSubmissionService._result_response(
            session,
            [],
            questions,
            attempts,
        )
    assert exc_info.value.code == "REVISION_SESSION_RESULT_UNAVAILABLE"
