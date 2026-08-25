def test_learning_item_create_read_delete_contract(client, registered_user) -> None:
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


def test_user_cannot_read_or_delete_another_users_item(client) -> None:
    first = client.post(
        "/register",
        params={"username": "one", "email": "one@example.test", "password": "pw"},
    ).json()
    second = client.post(
        "/register",
        params={"username": "two", "email": "two@example.test", "password": "pw"},
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
        params={"username": "label-owner", "email": "owner@example.test", "password": "pw"},
    ).json()
    second = client.post(
        "/register",
        params={"username": "attacker", "email": "attacker@example.test", "password": "pw"},
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
