def _create_label(db_session, user_id: int, name: str):
    from src.modules.labels.models import Label

    label = Label(user_id=user_id, label_name=name)
    db_session.add(label)
    db_session.flush()
    return label


def _create_item_with_questions(
    db_session,
    user_id: int,
    title: str,
    question_count: int,
    label_ids: list[int] | None = None,
):
    from src.modules.learning_items.models import LearningItem, LearningItemLabel
    from src.modules.revisions.models import Question

    item = LearningItem(user_id=user_id, title=title, description_text="Notes")
    db_session.add(item)
    db_session.flush()
    for label_id in label_ids or []:
        db_session.add(LearningItemLabel(learning_item_id=item.id, label_id=label_id))
    questions = []
    for index in range(question_count):
        question = Question(
            learning_item_id=item.id,
            question_text=f"{title} question {index + 1}?",
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


def _registered_user_id(db_session) -> int:
    from src.modules.auth.models import User

    return db_session.query(User.id).filter(User.username == "atul").scalar()


def test_revision_session_requires_authentication(client) -> None:
    assert client.post(
        "/revision-sessions",
        json={"quiz_type": "RANDOM", "question_count": 1},
    ).status_code == 401
    assert client.get("/revision-sessions/1").status_code == 401


def test_random_session_persists_safe_stable_order(
    client,
    registered_user,
    db_session,
) -> None:
    user_id = _registered_user_id(db_session)
    _create_item_with_questions(db_session, user_id, "Random", 4)
    db_session.commit()

    created = client.post(
        "/revision-sessions",
        json={
            "quiz_type": "RANDOM",
            "question_count": 3,
            "allow_ai_generation": True,
        },
        headers=registered_user["headers"],
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["requested_strategy"] == "RANDOM"
    assert payload["question_count"] == 3
    assert payload["questions_per_label"] is None
    assert payload["labels"] is None
    assert payload["generated_question_count"] == 0
    assert len(payload["questions"]) == 3

    for question in payload["questions"]:
        assert set(question) == {
            "session_question_id",
            "position",
            "question",
            "options",
            "difficulty",
            "expected_time_seconds",
        }
        assert "correct_option" not in question
        assert "explanation" not in question
        assert "question_id" not in question

    resumed = client.get(
        f"/revision-sessions/{payload['session_id']}",
        headers=registered_user["headers"],
    )
    assert resumed.status_code == 200
    assert resumed.json() == payload


def test_label_session_uses_strict_unique_quota_matching(
    client,
    registered_user,
    db_session,
) -> None:
    from src.modules.revisions.models import (
        RevisionSessionLabel,
        RevisionSessionQuestion,
    )

    user_id = _registered_user_id(db_session)
    first = _create_label(db_session, user_id, "Rich")
    second = _create_label(db_session, user_id, "Scarce")
    _create_item_with_questions(
        db_session,
        user_id,
        "Shared",
        2,
        [first.id, second.id],
    )
    _create_item_with_questions(db_session, user_id, "Rich only", 2, [first.id])
    db_session.commit()

    response = client.post(
        "/revision-sessions",
        json={
            "quiz_type": "LABEL",
            "label_ids": [first.id, second.id],
            "questions_per_label": 2,
            "allow_ai_generation": True,
        },
        headers=registered_user["headers"],
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["question_count"] == 4
    assert payload["questions_per_label"] == 2
    assert [label["label_id"] for label in payload["labels"]] == [first.id, second.id]
    assert len({question["session_question_id"] for question in payload["questions"]}) == 4

    session_labels = {
        label.id: label.label_id
        for label in db_session.query(RevisionSessionLabel)
        .filter(RevisionSessionLabel.session_id == payload["session_id"])
        .all()
    }
    assignments = (
        db_session.query(RevisionSessionQuestion)
        .filter(RevisionSessionQuestion.session_id == payload["session_id"])
        .order_by(RevisionSessionQuestion.question_order)
        .all()
    )
    assert [session_labels[row.session_label_id] for row in assignments] == [
        first.id,
        second.id,
        first.id,
        second.id,
    ]


def test_label_create_resume_submit_and_result_lifecycle(
    client,
    registered_user,
    fake_ai,
    db_session,
) -> None:
    user_id = _registered_user_id(db_session)
    label = _create_label(db_session, user_id, "Lifecycle")
    _create_item_with_questions(
        db_session,
        user_id,
        "Label lifecycle",
        2,
        [label.id],
    )
    db_session.commit()

    created_response = client.post(
        "/revision-sessions",
        json={
            "quiz_type": "LABEL",
            "label_ids": [label.id],
            "questions_per_label": 2,
            "allow_ai_generation": True,
        },
        headers=registered_user["headers"],
    )
    assert created_response.status_code == 201
    created = created_response.json()
    assert created["requested_strategy"] == "LABEL"
    assert created["strategy_used"] == "LABEL"
    assert created["labels"] == [
        {
            "label_id": label.id,
            "label_name": "Lifecycle",
            "question_quota": 2,
        }
    ]
    assert all("correct_option" not in row for row in created["questions"])
    assert all("explanation" not in row for row in created["questions"])
    assert fake_ai.calls == 0

    resumed = client.get(
        f"/revision-sessions/{created['session_id']}",
        headers=registered_user["headers"],
    )
    assert resumed.status_code == 200
    assert resumed.json() == created

    submitted = client.post(
        f"/revision-sessions/{created['session_id']}/submit",
        json={
            "answers": [
                {
                    "session_question_id": row["session_question_id"],
                    "selected_option": "B",
                    "time_taken_seconds": 10,
                }
                for row in created["questions"]
            ]
        },
        headers=registered_user["headers"],
    )
    assert submitted.status_code == 200
    result = submitted.json()
    assert result["requested_strategy"] == "LABEL"
    assert result["strategy_used"] == "LABEL"
    assert result["correct_count"] == 2
    assert result["question_count"] == 2
    assert all("correct_option" in row for row in result["questions"])
    assert all("explanation" in row for row in result["questions"])

    retrieved = client.get(
        f"/revision-sessions/{created['session_id']}/result",
        headers=registered_user["headers"],
    )
    assert retrieved.status_code == 200
    assert retrieved.json() == result


def test_label_shortage_persists_no_session_rows(
    client,
    registered_user,
    fake_ai,
    db_session,
) -> None:
    from src.modules.revisions.models import (
        RevisionSession,
        RevisionSessionLabel,
        RevisionSessionQuestion,
    )

    user_id = _registered_user_id(db_session)
    first = _create_label(db_session, user_id, "Enough")
    second = _create_label(db_session, user_id, "Short")
    _create_item_with_questions(db_session, user_id, "Enough", 2, [first.id])
    _create_item_with_questions(db_session, user_id, "Short", 1, [second.id])
    db_session.commit()

    response = client.post(
        "/revision-sessions",
        json={
            "quiz_type": "LABEL",
            "label_ids": [first.id, second.id],
            "questions_per_label": 2,
            "allow_ai_generation": True,
        },
        headers=registered_user["headers"],
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "INSUFFICIENT_QUESTION_BANK"
    assert detail["total_shortage"] == 1
    assert detail["ai_generation_available"] is False
    assert {row["label_id"]: row["shortage"] for row in detail["label_shortages"]} == {
        first.id: 0,
        second.id: 1,
    }
    assert fake_ai.calls == 0
    assert db_session.query(RevisionSession).count() == 0
    assert db_session.query(RevisionSessionLabel).count() == 0
    assert db_session.query(RevisionSessionQuestion).count() == 0


def test_random_excludes_malformed_legacy_questions(
    client,
    registered_user,
    db_session,
) -> None:
    from src.modules.revisions.models import Question, RevisionSession

    user_id = _registered_user_id(db_session)
    item, _questions = _create_item_with_questions(db_session, user_id, "Valid", 1)
    db_session.add(
        Question(
            learning_item_id=item.id,
            question_text="Malformed?",
            option_a="A",
            option_b="",
            option_c="C",
            option_d="D",
            correct_option="0",
            explanation="Invalid option",
            difficulty=1,
            expected_time_seconds=10,
            source="legacy",
        )
    )
    db_session.commit()

    response = client.post(
        "/revision-sessions",
        json={"quiz_type": "RANDOM", "question_count": 2},
        headers=registered_user["headers"],
    )
    assert response.status_code == 409
    assert response.json()["detail"]["assignable_question_count"] == 1
    assert db_session.query(RevisionSession).count() == 0


def test_foreign_label_and_session_are_concealed(
    client,
    registered_user,
    db_session,
) -> None:
    second_user = client.post(
        "/register",
        params={
            "username": "second",
            "email": "second@example.test",
            "password": "safe-password",
        },
    ).json()
    from src.modules.auth.models import User

    second_id = db_session.query(User.id).filter(User.username == "second").scalar()
    foreign_label = _create_label(db_session, second_id, "Private")
    db_session.commit()

    foreign_label_response = client.post(
        "/revision-sessions",
        json={
            "quiz_type": "LABEL",
            "label_ids": [foreign_label.id],
            "questions_per_label": 1,
        },
        headers=registered_user["headers"],
    )
    assert foreign_label_response.status_code == 404

    _create_item_with_questions(db_session, second_id, "Private item", 1)
    db_session.commit()
    created = client.post(
        "/revision-sessions",
        json={"quiz_type": "RANDOM", "question_count": 1},
        headers={"Authorization": f"Bearer {second_user['access_token']}"},
    ).json()
    assert client.get(
        f"/revision-sessions/{created['session_id']}",
        headers=registered_user["headers"],
    ).status_code == 404


def test_snapshot_survives_source_learning_item_deletion(
    client,
    registered_user,
    db_session,
) -> None:
    user_id = _registered_user_id(db_session)
    item, _questions = _create_item_with_questions(db_session, user_id, "History", 1)
    db_session.commit()
    response = client.post(
        "/revision-sessions",
        json={"quiz_type": "RANDOM", "question_count": 1},
        headers=registered_user["headers"],
    )
    payload = response.json()

    db_session.delete(item)
    db_session.commit()

    resumed = client.get(
        f"/revision-sessions/{payload['session_id']}",
        headers=registered_user["headers"],
    )
    assert resumed.status_code == 200
    assert resumed.json()["questions"] == payload["questions"]


def test_strategy_incompatible_fields_return_422(client, registered_user) -> None:
    assert client.post(
        "/revision-sessions",
        json={
            "quiz_type": "RANDOM",
            "question_count": 1,
            "questions_per_label": 1,
        },
        headers=registered_user["headers"],
    ).status_code == 422
    assert client.post(
        "/revision-sessions",
        json={
            "quiz_type": "LABEL",
            "label_ids": [1],
            "questions_per_label": 1,
            "question_count": 1,
        },
        headers=registered_user["headers"],
    ).status_code == 422
