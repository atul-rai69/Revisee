from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import inspect
from sqlalchemy.orm import Session


def _registered_user_id(db_session) -> int:
    from src.modules.auth.models import User

    return db_session.query(User.id).filter(User.username == "atul").scalar()


def _create_item_question(db_session, user_id: int, *, correct: str = "1"):
    from src.modules.learning_items.models import LearningItem
    from src.modules.revisions.models import Question

    item = LearningItem(user_id=user_id, title="Submission item", description_text="Notes")
    db_session.add(item)
    db_session.flush()
    question = Question(
        learning_item_id=item.id,
        question_text="Stored question?",
        option_a="A",
        option_b="B",
        option_c="C",
        option_d="D",
        correct_option=correct,
        explanation="Snapshot explanation",
        difficulty=2,
        expected_time_seconds=30,
        source="stored",
    )
    db_session.add(question)
    db_session.flush()
    return item, question


def _create_random_session(client, headers):
    response = client.post(
        "/revision-sessions",
        json={"quiz_type": "RANDOM", "question_count": 1},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_phase3_schema_structure_is_present(db_session) -> None:
    inspector = inspect(db_session.get_bind())
    assert "question_statistics" in inspector.get_table_names()
    attempt_columns = {
        column["name"] for column in inspector.get_columns("user_attempts")
    }
    assert {"session_question_id", "time_taken_seconds", "mastery_delta"} <= attempt_columns
    constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("user_attempts")
    }
    assert "uq_user_attempt_session_question" in constraints


def test_submission_requires_authentication(client) -> None:
    assert client.post(
        "/revision-sessions/1/submit",
        json={"answers": []},
    ).status_code == 401
    assert client.get("/revision-sessions/1/result").status_code == 401


def test_complete_submission_updates_attempt_statistics_and_mastery(
    client,
    registered_user,
    db_session,
) -> None:
    from src.modules.labels.models import Label
    from src.modules.learning_items.models import LearningItemLabel
    from src.modules.mastery.models import UserLabelMastery, UserLearningItemMastery
    from src.modules.revisions.models import QuestionStatistics, UserAttempt

    user_id = _registered_user_id(db_session)
    label = Label(user_id=user_id, label_name="Current label")
    db_session.add(label)
    db_session.flush()
    item, question = _create_item_question(db_session, user_id)
    db_session.add(LearningItemLabel(learning_item_id=item.id, label_id=label.id))
    db_session.commit()
    created = _create_random_session(client, registered_user["headers"])
    session_question_id = created["questions"][0]["session_question_id"]

    submitted = client.post(
        f"/revision-sessions/{created['session_id']}/submit",
        json={
            "answers": [
                {
                    "session_question_id": session_question_id,
                    "selected_option": "B",
                    "time_taken_seconds": 15,
                }
            ]
        },
        headers=registered_user["headers"],
    )
    assert submitted.status_code == 200
    result = submitted.json()
    assert result["status"] == "COMPLETED"
    assert result["correct_count"] == 1
    assert result["questions"][0]["correct_option"] == "B"
    assert result["questions"][0]["explanation"] == "Snapshot explanation"
    assert "question_id" not in result["questions"][0]

    attempt = db_session.query(UserAttempt).one()
    assert attempt.session_question_id == session_question_id
    assert attempt.mastery_delta == Decimal("7.50")
    statistics = db_session.get(QuestionStatistics, question.id)
    assert statistics.total_attempt_count == 1
    assert statistics.correct_attempt_count == 1
    assert statistics.total_time_seconds == 15
    assert statistics.average_time_seconds == Decimal("15.00")
    assert db_session.query(UserLearningItemMastery).one().mastery_score == Decimal("57.50")
    assert db_session.query(UserLabelMastery).one().mastery_score == Decimal("57.50")

    retrieved = client.get(
        f"/revision-sessions/{created['session_id']}/result",
        headers=registered_user["headers"],
    )
    assert retrieved.status_code == 200
    assert retrieved.json() == result
    resumed = client.get(
        f"/revision-sessions/{created['session_id']}",
        headers=registered_user["headers"],
    ).json()
    assert "correct_option" not in resumed["questions"][0]
    assert "explanation" not in resumed["questions"][0]


def test_exact_answer_set_and_repeated_submission_errors(
    client,
    registered_user,
    db_session,
) -> None:
    user_id = _registered_user_id(db_session)
    _create_item_question(db_session, user_id)
    db_session.commit()
    created = _create_random_session(client, registered_user["headers"])
    answer_id = created["questions"][0]["session_question_id"]

    incomplete_result = client.get(
        f"/revision-sessions/{created['session_id']}/result",
        headers=registered_user["headers"],
    )
    assert incomplete_result.status_code == 409
    assert (
        incomplete_result.json()["detail"]["code"]
        == "REVISION_SESSION_NOT_COMPLETED"
    )

    mismatch = client.post(
        f"/revision-sessions/{created['session_id']}/submit",
        json={
            "answers": [
                {
                    "session_question_id": answer_id + 9999,
                    "selected_option": "A",
                    "time_taken_seconds": 1,
                }
            ]
        },
        headers=registered_user["headers"],
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["detail"]["code"] == "ANSWER_SET_MISMATCH"

    payload = {
        "answers": [
            {
                "session_question_id": answer_id,
                "selected_option": "B",
                "time_taken_seconds": 10,
            }
        ]
    }
    assert client.post(
        f"/revision-sessions/{created['session_id']}/submit",
        json=payload,
        headers=registered_user["headers"],
    ).status_code == 200
    repeated = client.post(
        f"/revision-sessions/{created['session_id']}/submit",
        json=payload,
        headers=registered_user["headers"],
    )
    assert repeated.status_code == 409
    assert repeated.json()["detail"]["code"] == "REVISION_SESSION_ALREADY_COMPLETED"


def test_submission_failure_rolls_back_all_database_changes(
    client,
    registered_user,
    db_session,
    monkeypatch,
) -> None:
    from src.modules.mastery.models import UserLearningItemMastery
    from src.modules.revisions import submission_repository
    from src.modules.revisions.models import (
        QuestionStatistics,
        RevisionSession,
        UserAttempt,
    )

    user_id = _registered_user_id(db_session)
    _create_item_question(db_session, user_id)
    db_session.commit()
    created = _create_random_session(client, registered_user["headers"])

    def fail_statistics(*_args, **_kwargs):
        raise RuntimeError("synthetic statistics failure")

    monkeypatch.setattr(
        submission_repository,
        "upsert_question_statistics",
        fail_statistics,
    )
    response = client.post(
        f"/revision-sessions/{created['session_id']}/submit",
        json={
            "answers": [
                {
                    "session_question_id": created["questions"][0]["session_question_id"],
                    "selected_option": "B",
                    "time_taken_seconds": 10,
                }
            ]
        },
        headers=registered_user["headers"],
    )
    assert response.status_code == 500
    db_session.expire_all()
    session = db_session.get(RevisionSession, created["session_id"])
    assert session.status == "IN_PROGRESS"
    assert session.ended_at is None
    assert db_session.query(UserAttempt).count() == 0
    assert db_session.query(QuestionStatistics).count() == 0
    assert db_session.query(UserLearningItemMastery).count() == 0


def test_snapshot_result_survives_source_deletion(
    client,
    registered_user,
    db_session,
) -> None:
    from src.modules.mastery.models import UserLearningItemMastery
    from src.modules.revisions.models import QuestionStatistics

    user_id = _registered_user_id(db_session)
    item, question = _create_item_question(db_session, user_id, correct="A")
    db_session.commit()
    created = _create_random_session(client, registered_user["headers"])
    db_session.delete(item)
    db_session.commit()

    submitted = client.post(
        f"/revision-sessions/{created['session_id']}/submit",
        json={
            "answers": [
                {
                    "session_question_id": created["questions"][0]["session_question_id"],
                    "selected_option": "A",
                    "time_taken_seconds": 10,
                }
            ]
        },
        headers=registered_user["headers"],
    )
    assert submitted.status_code == 200
    assert submitted.json()["questions"][0]["is_correct"] is True
    assert db_session.get(QuestionStatistics, question.id) is None
    assert db_session.query(UserLearningItemMastery).count() == 0


def test_deleted_live_question_still_grades_snapshot_and_updates_item_mastery(
    client,
    registered_user,
    db_session,
) -> None:
    from src.modules.mastery.models import UserLearningItemMastery
    from src.modules.revisions.models import QuestionStatistics

    user_id = _registered_user_id(db_session)
    item, question = _create_item_question(db_session, user_id, correct="1")
    item_id = item.id
    question_id = question.id
    db_session.commit()
    created = _create_random_session(client, registered_user["headers"])
    db_session.delete(question)
    db_session.commit()

    submitted = client.post(
        f"/revision-sessions/{created['session_id']}/submit",
        json={
            "answers": [
                {
                    "session_question_id": created["questions"][0]["session_question_id"],
                    "selected_option": "B",
                    "time_taken_seconds": 15,
                }
            ]
        },
        headers=registered_user["headers"],
    )
    assert submitted.status_code == 200
    assert submitted.json()["questions"][0]["is_correct"] is True
    assert db_session.get(QuestionStatistics, question_id) is None
    mastery = db_session.query(UserLearningItemMastery).one()
    assert mastery.learning_item_id == item_id
    assert mastery.mastery_score == Decimal("57.50")


def test_foreign_session_is_concealed_for_submit_and_result(
    client,
    registered_user,
    db_session,
) -> None:
    second = client.post(
        "/register",
        json={
            "username": "submission-second",
            "email": "submission-second@example.test",
            "password": "safe-password",
        },
    ).json()
    from src.modules.auth.models import User

    second_id = db_session.query(User.id).filter_by(username="submission-second").scalar()
    _create_item_question(db_session, second_id)
    db_session.commit()
    created = _create_random_session(
        client,
        {"Authorization": f"Bearer {second['access_token']}"},
    )
    assert client.get(
        f"/revision-sessions/{created['session_id']}/result",
        headers=registered_user["headers"],
    ).status_code == 404
    assert client.post(
        f"/revision-sessions/{created['session_id']}/submit",
        json={
            "answers": [
                {
                    "session_question_id": created["questions"][0]["session_question_id"],
                    "selected_option": "A",
                    "time_taken_seconds": 1,
                }
            ]
        },
        headers=registered_user["headers"],
    ).status_code == 404


def test_concurrent_submission_allows_exactly_one_commit(migrated_database) -> None:
    from src.db.session import engine
    from src.modules.auth.models import User
    from src.modules.learning_items.models import LearningItem
    from src.modules.revisions.models import Question, RevisionSession, RevisionSessionQuestion
    from src.modules.revisions.submission_schemas import RevisionSessionSubmitRequest
    from src.modules.revisions.submission_service import (
        RevisionSubmissionError,
        RevisionSubmissionService,
    )

    unique = uuid4().hex
    with Session(engine) as setup:
        user = User(
            username=f"concurrent-{unique}",
            email=f"concurrent-{unique}@example.test",
            password_hash="test-only-not-a-real-login",
        )
        setup.add(user)
        setup.flush()
        item = LearningItem(user_id=user.id, title="Concurrent", description_text="Notes")
        setup.add(item)
        setup.flush()
        question = Question(
            learning_item_id=item.id,
            question_text="Concurrent?",
            option_a="A",
            option_b="B",
            option_c="C",
            option_d="D",
            correct_option="0",
            explanation="A",
            difficulty=1,
            expected_time_seconds=20,
            source="stored",
        )
        setup.add(question)
        setup.flush()
        session = RevisionSession(
            user_id=user.id,
            quiz_type="RANDOM",
            requested_strategy="RANDOM",
            strategy_used="RANDOM",
            status="IN_PROGRESS",
            requested_question_count=1,
            generated_question_count=0,
            allow_ai_generation=False,
        )
        setup.add(session)
        setup.flush()
        selected = RevisionSessionQuestion(
            session_id=session.id,
            question_id=question.id,
            learning_item_id=item.id,
            question_order=1,
            learning_item_title_snapshot=item.title,
            question_text_snapshot=question.question_text,
            option_a_snapshot="A",
            option_b_snapshot="B",
            option_c_snapshot="C",
            option_d_snapshot="D",
            correct_option_snapshot="0",
            explanation_snapshot="A",
            difficulty_snapshot=1,
            expected_time_seconds_snapshot=20,
            source_snapshot="stored",
            generated_for_session=False,
        )
        setup.add(selected)
        setup.commit()
        user_id, session_id, selected_id = user.id, session.id, selected.id

    request = RevisionSessionSubmitRequest.model_validate(
        {
            "answers": [
                {
                    "session_question_id": selected_id,
                    "selected_option": "A",
                    "time_taken_seconds": 10,
                }
            ]
        }
    )

    def submit_once():
        with Session(engine) as db:
            try:
                RevisionSubmissionService(db).submit(user_id, session_id, request)
                return "completed"
            except RevisionSubmissionError as exc:
                return exc.code

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _index: submit_once(), range(2)))
        assert sorted(outcomes) == [
            "REVISION_SESSION_ALREADY_COMPLETED",
            "completed",
        ]
    finally:
        with Session(engine) as cleanup:
            cleanup.query(User).filter(User.id == user_id).delete()
            cleanup.commit()
