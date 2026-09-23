import pytest
from sqlalchemy import text


def test_learning_item_create_read_delete_contract(
    client,
    registered_user,
    db_session,
) -> None:
    headers = registered_user["headers"]
    created = client.post(
        "/learning-items",
        data={
            "title": "Cells",
            "description_text": "Cell notes",
            "labels": "[]",
        },
        headers=headers,
    )
    assert created.status_code == 200
    assert created.json() == {"message": "Learning item created"}

    summary = client.get("/dashboard/learning-items-summary", headers=headers)
    item_id = summary.json()["data"][0]["id"]
    assert db_session.scalar(
        text(
            "SELECT COUNT(*) FROM learning_item_key_points "
            "WHERE learning_item_id = :item_id"
        ),
        {"item_id": item_id},
    ) > 0

    detail = client.get(f"/learning-item/{item_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["questions"][0]["options"][1]["isCorrect"]

    deleted = client.request(
        "DELETE",
        "/learning-items",
        json={"id": item_id},
        headers=headers,
    )
    assert deleted.status_code == 200
    assert deleted.json() is None
    assert db_session.scalar(
        text(
            "SELECT COUNT(*) FROM learning_item_key_points "
            "WHERE learning_item_id = :item_id"
        ),
        {"item_id": item_id},
    ) == 0


def test_user_cannot_read_or_delete_another_users_item(client) -> None:
    first = client.post(
        "/register",
        json={"username": "one", "email": "one@example.test", "password": "safe-password"},
    ).json()
    second = client.post(
        "/register",
        json={"username": "two", "email": "two@example.test", "password": "safe-password"},
    ).json()
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}

    client.post(
        "/learning-items",
        data={"title": "Private", "description_text": "Notes", "labels": "[]"},
        headers=first_headers,
    )
    item_id = client.get(
        "/dashboard/learning-items-summary", headers=first_headers
    ).json()["data"][0]["id"]

    assert client.get(f"/learning-item/{item_id}", headers=second_headers).status_code == 404
    assert client.request(
        "DELETE", "/learning-items", json={"id": item_id}, headers=second_headers
    ).status_code == 404
    assert client.post(
        "/generate",
        json={
            "learning_item_id": item_id,
            "title": "Private",
            "description": "Notes",
        },
        headers=second_headers,
    ).status_code == 404


def test_user_cannot_attach_another_users_label(client, fake_ai) -> None:
    first = client.post(
        "/register",
        json={"username": "label-owner", "email": "owner@example.test", "password": "safe-password"},
    ).json()
    second = client.post(
        "/register",
        json={"username": "attacker", "email": "attacker@example.test", "password": "safe-password"},
    ).json()
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}
    label = client.post(
        "/labels", json={"label_name": "Private"}, headers=first_headers
    ).json()["label"]

    response = client.post(
        "/learning-items",
        data={
            "title": "Invalid",
            "description_text": "Notes",
            "labels": f"[{label['id']}]",
        },
        headers=second_headers,
    )
    assert response.status_code == 404
    assert fake_ai.calls == 0


def test_upload_failure_compensates_previous_upload(
    client,
    registered_user,
    fake_storage,
) -> None:
    fake_storage.fail_on_upload_number = 2
    response = client.post(
        "/learning-items",
        data={"title": "Media", "description_text": "Notes", "labels": "[]"},
        files=[
            ("images", ("one.png", b"one", "image/png")),
            ("images", ("two.png", b"two", "image/png")),
        ],
        headers=registered_user["headers"],
    )
    assert response.status_code == 502
    assert fake_storage.deletes == [("test-1", "image")]


def test_database_work_failure_compensates_uploads(
    client,
    registered_user,
    fake_storage,
    monkeypatch,
) -> None:
    from src.modules.revisions import repository as revision_repository

    def fail_persistence(*_args, **_kwargs):
        raise RuntimeError("synthetic persistence failure")

    monkeypatch.setattr(
        revision_repository,
        "add_generated_content",
        fail_persistence,
    )
    response = client.post(
        "/learning-items",
        data={"title": "Rollback", "description_text": "Notes", "labels": "[]"},
        files=[("images", ("one.png", b"one", "image/png"))],
        headers=registered_user["headers"],
    )
    assert response.status_code == 500
    assert fake_storage.deletes == [("test-1", "image")]


@pytest.mark.parametrize(
    ("field_name", "filename", "content_type", "setting_name", "media_label"),
    [
        ("images", "large.png", "image/png", "CLOUDINARY_MAX_IMAGE_BYTES", "image"),
        ("pdfs", "large.pdf", "application/pdf", "CLOUDINARY_MAX_RAW_BYTES", "PDF"),
    ],
)
def test_oversized_media_is_rejected_before_generation_or_upload(
    client,
    registered_user,
    fake_ai,
    fake_storage,
    field_name: str,
    filename: str,
    content_type: str,
    setting_name: str,
    media_label: str,
) -> None:
    from src.core.config import get_settings
    from src.main import app

    one_megabyte = 1024 * 1024
    settings = get_settings().model_copy(update={setting_name: one_megabyte})
    app.dependency_overrides[get_settings] = lambda: settings

    response = client.post(
        "/learning-items",
        data={"title": "Large media", "description_text": "Notes", "labels": "[]"},
        files=[(field_name, (filename, b"x" * (one_megabyte + 1), content_type))],
        headers=registered_user["headers"],
    )

    assert response.status_code == 422
    assert response.json()["detail"] == f"Each {media_label} must be 1 MB or smaller"
    assert fake_ai.calls == 0
    assert fake_storage.uploads == []


def test_media_at_configured_size_limit_is_accepted(
    client,
    registered_user,
    fake_ai,
    fake_storage,
) -> None:
    from src.core.config import get_settings
    from src.main import app

    one_megabyte = 1024 * 1024
    settings = get_settings().model_copy(
        update={"CLOUDINARY_MAX_RAW_BYTES": one_megabyte}
    )
    app.dependency_overrides[get_settings] = lambda: settings

    response = client.post(
        "/learning-items",
        data={"title": "Boundary PDF", "description_text": "Notes", "labels": "[]"},
        files=[("pdfs", ("boundary.pdf", b"x" * one_megabyte, "application/pdf"))],
        headers=registered_user["headers"],
    )

    assert response.status_code == 200
    assert fake_ai.calls == 1
    assert len(fake_storage.uploads) == 1
