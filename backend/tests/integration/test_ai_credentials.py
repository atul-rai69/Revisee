from sqlalchemy import func, select

from src.modules.ai_credentials.models import AICredential, AICredentialUsage
from src.modules.learning_items.models import LearningItem
from src.modules.revisions.models import Question


def _register(client, username: str) -> dict[str, str]:
    response = client.post(
        "/register",
        json={
            "username": username,
            "email": f"{username}@example.test",
            "password": "safe-password",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_credential(client, headers, name: str, key: str, default=False):
    return client.post(
        "/ai-credentials",
        json={
            "provider": "GEMINI",
            "name": name,
            "api_key": key,
            "make_default": default,
        },
        headers=headers,
    )


def test_credentials_are_encrypted_masked_and_owned(client, db_session) -> None:
    owner = _register(client, "key-owner")
    other = _register(client, "key-other")
    plaintext = "owner-gemini-key-123456"
    created = _create_credential(client, owner, "Primary", plaintext, True)
    assert created.status_code == 201
    payload = created.json()
    credential_id = payload["id"]
    assert payload["masked_identifier"] == "•••• 3456"
    assert payload["is_default"] is True
    assert "api_key" not in payload
    assert plaintext not in created.text

    stored = db_session.get(AICredential, credential_id)
    assert stored is not None
    assert plaintext.encode() not in stored.encrypted_secret
    assert stored.encrypted_secret != plaintext.encode()

    owner_list = client.get("/ai-credentials", headers=owner)
    assert owner_list.status_code == 200
    assert [entry["id"] for entry in owner_list.json()["credentials"]] == [credential_id]
    assert plaintext not in owner_list.text
    assert client.get("/ai-credentials", headers=other).json()["credentials"] == []

    assert client.patch(
        f"/ai-credentials/{credential_id}",
        json={"name": "stolen"},
        headers=other,
    ).status_code == 404
    assert client.put(
        f"/ai-credentials/{credential_id}/default", json={}, headers=other
    ).status_code == 404
    assert client.delete(
        f"/ai-credentials/{credential_id}", headers=other
    ).status_code == 404


def test_replace_default_and_delete_behaviour(client) -> None:
    headers = _register(client, "key-rotation")
    first = _create_credential(
        client, headers, "First", "first-gemini-key-1234", True
    ).json()
    second = _create_credential(
        client, headers, "Second", "second-gemini-key-5678"
    ).json()

    selected = client.put(
        f"/ai-credentials/{second['id']}/default", json={}, headers=headers
    )
    assert selected.status_code == 200
    assert selected.json()["is_default"] is True

    replaced = client.patch(
        f"/ai-credentials/{second['id']}",
        json={"name": "Rotated", "api_key": "replacement-key-9012"},
        headers=headers,
    )
    assert replaced.status_code == 200
    assert replaced.json()["name"] == "Rotated"
    assert replaced.json()["masked_identifier"] == "•••• 9012"
    assert "replacement-key-9012" not in replaced.text

    deleted = client.delete(f"/ai-credentials/{second['id']}", headers=headers)
    assert deleted.status_code == 204
    remaining = client.get("/ai-credentials", headers=headers).json()["credentials"]
    assert len(remaining) == 1
    assert remaining[0]["id"] == first["id"]
    assert remaining[0]["is_default"] is True


def test_personal_question_generation_is_append_only_and_records_usage(
    client,
    db_session,
) -> None:
    headers = _register(client, "personal-generation")
    credential = _create_credential(
        client, headers, "Study", "personal-study-key-1234", True
    ).json()
    created = client.post(
        "/learning-items",
        data={
            "title": "Networks",
            "description_text": "Owned notes",
            "labels": "[]",
        },
        headers=headers,
    )
    assert created.status_code == 200
    item = db_session.scalar(select(LearningItem).where(LearningItem.title == "Networks"))
    assert item is not None
    original_theory = item.theory
    original_notes = item.description_text
    original_count = db_session.scalar(
        select(func.count(Question.id)).where(Question.learning_item_id == item.id)
    )

    generated = client.post(
        f"/learning-items/{item.id}/generated-questions",
        json={
            "question_count": 3,
            "generation_source": "PERSONAL",
            "credential_id": credential["id"],
            "personal_remarks": "Prefer practical examples.",
        },
        headers=headers,
    )
    assert generated.status_code == 200
    assert generated.json()["saved_count"] == 1
    db_session.refresh(item)
    assert item.theory == original_theory
    assert item.description_text == original_notes
    assert db_session.scalar(
        select(func.count(Question.id)).where(Question.learning_item_id == item.id)
    ) == original_count + 1
    assert db_session.scalar(
        select(func.count(AICredentialUsage.id)).where(
            AICredentialUsage.credential_id == credential["id"]
        )
    ) == 1


def test_learning_item_creation_can_use_an_owned_personal_credential(
    client,
    db_session,
) -> None:
    headers = _register(client, "personal-item")
    credential = _create_credential(
        client, headers, "Creation", "personal-create-key-1234", True
    ).json()
    response = client.post(
        "/learning-items",
        data={
            "title": "Personal generation",
            "description_text": "Text source sent with explicit consent.",
            "labels": "[]",
            "generation_source": "PERSONAL",
            "credential_id": credential["id"],
            "personal_remarks": "Use a concise teaching style.",
        },
        headers=headers,
    )
    assert response.status_code == 200
    item = db_session.scalar(
        select(LearningItem).where(LearningItem.title == "Personal generation")
    )
    assert item is not None
    assert item.theory == "Generated theory"
    assert db_session.scalar(
        select(func.count(AICredentialUsage.id)).where(
            AICredentialUsage.credential_id == credential["id"]
        )
    ) == 1


def test_personal_generation_rejects_another_users_credential(client) -> None:
    owner = _register(client, "credential-source")
    other = _register(client, "credential-attacker")
    credential = _create_credential(
        client, owner, "Private", "private-gemini-key-1234", True
    ).json()
    client.post(
        "/learning-items",
        data={"title": "Other item", "description_text": "Notes", "labels": "[]"},
        headers=other,
    )
    item_id = client.get(
        "/dashboard/learning-items-summary", headers=other
    ).json()["data"][0]["id"]
    response = client.post(
        f"/learning-items/{item_id}/generated-questions",
        json={
            "question_count": 1,
            "generation_source": "PERSONAL",
            "credential_id": credential["id"],
            "personal_remarks": None,
        },
        headers=other,
    )
    assert response.status_code == 404


def test_invalid_key_is_not_saved(client) -> None:
    headers = _register(client, "invalid-key")
    response = _create_credential(
        client, headers, "Invalid", "invalid-test-key", True
    )
    assert response.status_code == 422
    assert client.get("/ai-credentials", headers=headers).json()["credentials"] == []
