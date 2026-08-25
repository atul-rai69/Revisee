def test_generate_requires_authentication(client) -> None:
    response = client.post(
        "/generate",
        json={"learning_item_id": 1, "title": "Title", "description": "Notes"},
    )
    assert response.status_code == 401


def test_invalid_provider_output_persists_nothing(
    client,
    registered_user,
    fake_ai,
    db_session,
) -> None:
    from src.modules.learning_items.models import LearningItem

    fake_ai.raw_response = "not-json"
    response = client.post(
        "/learning-items",
        data={"title": "Invalid AI", "description_text": "Notes", "labels": "[]"},
        headers=registered_user["headers"],
    )
    assert response.status_code == 502
    assert db_session.query(LearningItem).count() == 0
