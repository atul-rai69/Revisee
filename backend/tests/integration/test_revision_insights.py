def _user_id(db_session, username: str = "atul") -> int:
    from src.modules.auth.models import User

    return db_session.query(User.id).filter(User.username == username).scalar()


def _owned_item(db_session, user_id: int, title: str):
    from src.modules.learning_items.models import LearningItem

    item = LearningItem(user_id=user_id, title=title, description_text="Owned notes")
    db_session.add(item)
    db_session.flush()
    return item


def _question_payload(text: str = "What is the answer?") -> dict[str, object]:
    return {
        "question": text,
        "option_a": "Alpha",
        "option_b": "Beta",
        "option_c": "Gamma",
        "option_d": "Delta",
        "correct_option": "A",
        "explanation": "Alpha is correct.",
        "difficulty": 2,
        "expected_time_seconds": 30,
    }


def test_owned_history_manual_questions_statistics_and_mastery(
    client, registered_user, db_session
) -> None:
    from src.modules.labels.models import Label
    from src.modules.learning_items.models import LearningItemLabel

    user_id = _user_id(db_session)
    item = _owned_item(db_session, user_id, "Databases")
    empty_item = _owned_item(db_session, user_id, "No questions")
    databases = Label(user_id=user_id, label_name="Databases")
    programming = Label(user_id=user_id, label_name="Programming")
    db_session.add_all([databases, programming])
    db_session.flush()
    db_session.add_all([
        LearningItemLabel(learning_item_id=item.id, label_id=databases.id),
        LearningItemLabel(learning_item_id=item.id, label_id=programming.id),
    ])
    db_session.commit()

    payload = _question_payload()
    created_question = client.post(
        f"/learning-items/{item.id}/questions",
        json=payload,
        headers=registered_user["headers"],
    )
    assert created_question.status_code == 201
    assert client.post(
        f"/learning-items/{item.id}/questions",
        json=payload,
        headers=registered_user["headers"],
    ).status_code == 409
    invalid = dict(payload)
    invalid["option_d"] = "  "
    assert client.post(
        f"/learning-items/{item.id}/questions",
        json=invalid,
        headers=registered_user["headers"],
    ).status_code == 422

    first = client.post(
        "/revision-sessions",
        json={"quiz_type": "RANDOM", "question_count": 1},
        headers=registered_user["headers"],
    ).json()
    submitted = client.post(
        f"/revision-sessions/{first['session_id']}/submit",
        json={"answers": [{
            "session_question_id": first["questions"][0]["session_question_id"],
            "selected_option": "A",
            "time_taken_seconds": 12,
        }]},
        headers=registered_user["headers"],
    )
    assert submitted.status_code == 200

    active = client.post(
        "/revision-sessions",
        json={"quiz_type": "RANDOM", "question_count": 1},
        headers=registered_user["headers"],
    ).json()
    history = client.get(
        "/revision-sessions?limit=1&offset=0",
        headers=registered_user["headers"],
    ).json()
    assert history["total"] == 2
    assert history["items"][0]["session_id"] == active["session_id"]
    assert history["items"][0]["score_percentage"] is None
    completed = client.get(
        "/revision-sessions?status=COMPLETED",
        headers=registered_user["headers"],
    ).json()
    assert completed["total"] == 1
    assert completed["items"][0]["correct_count"] == 1
    assert completed["items"][0]["score_percentage"] == 100.0

    detail = client.get(
        f"/learning-item/{item.id}", headers=registered_user["headers"]
    ).json()["data"]
    assert detail["questions"][0]["total_attempts"] == 1
    assert detail["questions"][0]["correct_attempts"] == 1
    assert detail["questions"][0]["accuracy_percent"] == 100.0

    analytics = client.get(
        "/mastery/analytics?entity_type=LEARNING_ITEM",
        headers=registered_user["headers"],
    ).json()
    by_name = {entry["display_name"]: entry for entry in analytics["items"]}
    assert by_name["Databases"]["evidence_status"] == "INSUFFICIENT_EVIDENCE"
    assert by_name["Databases"]["mastery_score"] is None
    assert len(by_name["Databases"]["trend"]) == 1
    assert by_name["No questions"]["evidence_status"] == "NO_QUESTIONS"
    assert by_name["No questions"]["mastery_score"] is None

    revision_responses = [
        client.get(
            f"/analytics/revision-activity?session_limit={session_limit}",
            headers=registered_user["headers"],
        )
        for session_limit in (7, 30, 50)
    ]
    assert all(response.status_code == 200 for response in revision_responses)
    assert [
        response.json()["requested_session_limit"] for response in revision_responses
    ] == [7, 30, 50]
    revision_analytics = revision_responses[0].json()
    assert revision_analytics["completed_session_count"] == 1
    assert revision_analytics["sessions_used"] == 1
    assert revision_analytics["activity"] == [{
        "date": submitted.json()["completed_at"][:10],
        "completed_session_count": 1,
        "answered_count": 1,
        "correct_count": 1,
        "accuracy_percent": 100.0,
    }]
    assert {
        point["topic_name"]: (
            point["attempt_count"], point["correct_count"], point["session_count"]
        )
        for point in revision_analytics["topic_practice"]
    } == {"Databases": (1, 1, 1), "Programming": (1, 1, 1)}
    assert "totals can overlap" in revision_analytics["attribution_note"]
    assert client.get(
        "/analytics/revision-activity?session_limit=8",
        headers=registered_user["headers"],
    ).status_code == 422


def test_history_and_manual_question_ownership_isolation(
    client, registered_user, db_session
) -> None:
    first_user_id = _user_id(db_session)
    first_item = _owned_item(db_session, first_user_id, "Private")
    db_session.commit()
    second = client.post(
        "/register",
        json={"username": "other", "email": "other@example.test", "password": "safe-password"},
    ).json()
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}
    assert client.post(
        f"/learning-items/{first_item.id}/questions",
        json=_question_payload(),
        headers=second_headers,
    ).status_code == 404
    assert client.get(
        "/revision-sessions", headers=second_headers
    ).json()["items"] == []
    for session_limit in (7, 30, 50):
        private_response = client.get(
            f"/analytics/revision-activity?session_limit={session_limit}",
            headers=second_headers,
        )
        assert private_response.status_code == 200
        private_analytics = private_response.json()
        assert private_analytics["requested_session_limit"] == session_limit
        assert private_analytics["completed_session_count"] == 0
        assert private_analytics["activity"] == []
        assert private_analytics["topic_practice"] == []


def test_smart_readiness_reports_actual_question_units(
    client, registered_user, db_session
) -> None:
    user_id = _user_id(db_session)
    item = _owned_item(db_session, user_id, "Readiness")
    db_session.commit()
    payload = _question_payload("Ready?")
    assert client.post(
        f"/learning-items/{item.id}/questions",
        json=payload,
        headers=registered_user["headers"],
    ).status_code == 201
    not_ready = client.get(
        "/revision-sessions/smart-readiness?question_count=2",
        headers=registered_user["headers"],
    ).json()
    assert not_ready["can_start"] is False
    assert not_ready["eligible_question_count"] == 1
    ready_for_fallback = client.get(
        "/revision-sessions/smart-readiness?question_count=1",
        headers=registered_user["headers"],
    ).json()
    assert ready_for_fallback["can_start"] is True
    assert ready_for_fallback["strategy_if_started"] == "RANDOM"
    assert ready_for_fallback["evidence_ready_learning_item_count"] == 0
    assert ready_for_fallback["minimum_attempts_per_item"] == 3
