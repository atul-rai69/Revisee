from decimal import Decimal

from sqlalchemy import inspect


def _registered_user_id(db_session) -> int:
    from src.modules.auth.models import User

    return db_session.query(User.id).filter(User.username == "atul").scalar()


def _item_with_questions(db_session, user_id: int, title: str, count: int):
    from src.modules.learning_items.models import LearningItem
    from src.modules.revisions.models import Question

    item = LearningItem(user_id=user_id, title=title, description_text="notes")
    db_session.add(item)
    db_session.flush()
    questions = []
    for index in range(count):
        question = Question(
            learning_item_id=item.id,
            question_text=f"{title} {index}?",
            option_a="A",
            option_b="B",
            option_c="C",
            option_d="D",
            correct_option="1",
            explanation="B is correct",
            difficulty=2,
            expected_time_seconds=30,
            source="stored",
        )
        db_session.add(question)
        questions.append(question)
    db_session.flush()
    return item, questions


def test_phase4_strategy_constraints_allow_smart(db_session) -> None:
    checks = {
        row["name"]: row["sqltext"]
        for row in inspect(db_session.get_bind()).get_check_constraints(
            "revision_sessions"
        )
    }
    assert "SMART" in checks["ck_revision_session_requested_strategy"]
    assert "SMART" in checks["ck_revision_session_strategy_used"]


def test_smart_create_resume_submit_and_result_remain_snapshot_safe(
    client,
    registered_user,
    fake_ai,
    db_session,
) -> None:
    from src.modules.mastery.models import UserLearningItemMastery

    user_id = _registered_user_id(db_session)
    weak, _ = _item_with_questions(db_session, user_id, "Weak", 2)
    _item_with_questions(db_session, user_id, "Explore", 2)
    db_session.add(
        UserLearningItemMastery(
            user_id=user_id,
            learning_item_id=weak.id,
            mastery_score=Decimal("20.00"),
            total_attempts=3,
            correct_attempts=1,
        )
    )
    db_session.commit()

    created = client.post(
        "/revision-sessions",
        json={
            "quiz_type": "SMART",
            "question_count": 3,
            "allow_ai_generation": True,
        },
        headers=registered_user["headers"],
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["requested_strategy"] == "SMART"
    assert payload["strategy_used"] == "SMART"
    assert fake_ai.calls == 0
    assert all("correct_option" not in row for row in payload["questions"])
    assert client.get(
        f"/revision-sessions/{payload['session_id']}",
        headers=registered_user["headers"],
    ).json() == payload

    submitted = client.post(
        f"/revision-sessions/{payload['session_id']}/submit",
        json={
            "answers": [
                {
                    "session_question_id": row["session_question_id"],
                    "selected_option": "B",
                    "time_taken_seconds": 10,
                }
                for row in payload["questions"]
            ]
        },
        headers=registered_user["headers"],
    )
    assert submitted.status_code == 200
    assert submitted.json()["requested_strategy"] == "SMART"
    assert submitted.json()["strategy_used"] == "SMART"
    assert client.get(
        f"/revision-sessions/{payload['session_id']}/result",
        headers=registered_user["headers"],
    ).json() == submitted.json()


def test_smart_random_fallback_and_total_bank_shortage(
    client,
    registered_user,
    db_session,
) -> None:
    user_id = _registered_user_id(db_session)
    _item_with_questions(db_session, user_id, "No evidence", 2)
    db_session.commit()

    fallback = client.post(
        "/revision-sessions",
        json={"quiz_type": "SMART", "question_count": 2},
        headers=registered_user["headers"],
    )
    assert fallback.status_code == 201
    assert fallback.json()["requested_strategy"] == "SMART"
    assert fallback.json()["strategy_used"] == "RANDOM"

    shortage = client.post(
        "/revision-sessions",
        json={"quiz_type": "SMART", "question_count": 3},
        headers=registered_user["headers"],
    )
    assert shortage.status_code == 409
    assert shortage.json()["detail"]["assignable_question_count"] == 2


def test_smart_bank_excludes_foreign_and_malformed_questions(
    client,
    registered_user,
    db_session,
) -> None:
    from src.modules.auth.models import User
    from src.modules.revisions.models import Question, RevisionSession

    user_id = _registered_user_id(db_session)
    item, _ = _item_with_questions(db_session, user_id, "Owned", 1)
    db_session.add(
        Question(
            learning_item_id=item.id,
            question_text="Malformed?",
            option_a="A",
            option_b="",
            option_c="C",
            option_d="D",
            correct_option="0",
            explanation="invalid",
            difficulty=1,
            expected_time_seconds=10,
            source="legacy",
        )
    )
    foreign = User(
        username="smart-foreign",
        email="smart-foreign@example.test",
        password_hash="not-used",
    )
    db_session.add(foreign)
    db_session.flush()
    _item_with_questions(db_session, foreign.id, "Foreign", 2)
    db_session.commit()

    response = client.post(
        "/revision-sessions",
        json={"quiz_type": "SMART", "question_count": 2},
        headers=registered_user["headers"],
    )
    assert response.status_code == 409
    assert response.json()["detail"]["assignable_question_count"] == 1
    assert db_session.query(RevisionSession).count() == 0
