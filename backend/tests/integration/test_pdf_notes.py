from sqlalchemy import text


def _create_item_with_pdf(client, headers, db_session, title: str = "PDF notes") -> tuple[int, int]:
    response = client.post(
        "/learning-items",
        data={"title": title, "description_text": "Source notes", "labels": "[]"},
        files=[("pdfs", ("Biology Revision Notes.pdf", b"%PDF-test", "application/pdf"))],
        headers=headers,
    )
    assert response.status_code == 200
    item_id = client.get(
        "/dashboard/learning-items-summary", headers=headers
    ).json()["data"][0]["id"]
    media_id = db_session.scalar(
        text(
            "SELECT id FROM media WHERE learning_item_id = :item_id "
            "AND type = 'pdf' ORDER BY id LIMIT 1"
        ),
        {"item_id": item_id},
    )
    assert media_id is not None
    return item_id, int(media_id)


def test_pdf_note_create_edit_list_delete_and_attachment_contract(
    client,
    registered_user,
    db_session,
) -> None:
    headers = registered_user["headers"]
    item_id, media_id = _create_item_with_pdf(client, headers, db_session)

    detail = client.get(f"/learning-item/{item_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["pdf_resources"] == [
        {
            "id": media_id,
            "url": "https://storage.test/1",
            "original_filename": "Biology Revision Notes.pdf",
        }
    ]
    assert db_session.scalar(
        text("SELECT original_filename FROM media WHERE id = :media_id"),
        {"media_id": media_id},
    ) == "Biology Revision Notes.pdf"

    created = client.post(
        f"/learning-items/{item_id}/pdf-notes",
        json={
            "media_id": media_id,
            "page_number": 3,
            "source_excerpt": "  A selected source passage.  ",
            "note_text": "  My own explanation.  ",
        },
        headers=headers,
    )
    assert created.status_code == 201
    note = created.json()
    assert note["source_excerpt"] == "A selected source passage."
    assert note["note_text"] == "My own explanation."
    assert note["media_id"] == media_id
    assert note["page_number"] == 3

    listed = client.get(f"/learning-items/{item_id}/pdf-notes", headers=headers)
    assert listed.status_code == 200
    assert [entry["id"] for entry in listed.json()["notes"]] == [note["id"]]

    updated = client.patch(
        f"/learning-items/{item_id}/pdf-notes/{note['id']}",
        json={"source_excerpt": None, "note_text": "Revised personal note"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["source_excerpt"] is None
    assert updated.json()["note_text"] == "Revised personal note"

    deleted = client.delete(
        f"/learning-items/{item_id}/pdf-notes/{note['id']}", headers=headers
    )
    assert deleted.status_code == 204
    assert client.get(
        f"/learning-items/{item_id}/pdf-notes", headers=headers
    ).json() == {"notes": []}


def test_pdf_notes_enforce_user_item_and_pdf_ownership(client, db_session) -> None:
    first = client.post(
        "/register",
        json={"username": "pdf-owner", "email": "pdf-owner@example.test", "password": "safe-password"},
    ).json()
    second = client.post(
        "/register",
        json={"username": "pdf-other", "email": "pdf-other@example.test", "password": "safe-password"},
    ).json()
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}
    first_item, first_media = _create_item_with_pdf(client, first_headers, db_session, "First PDF")
    second_item, second_media = _create_item_with_pdf(client, second_headers, db_session, "Second PDF")

    assert client.post(
        f"/learning-items/{first_item}/pdf-notes",
        json={
            "media_id": second_media,
            "page_number": 1,
            "source_excerpt": None,
            "note_text": "Cross-item attempt",
        },
        headers=first_headers,
    ).status_code == 404

    created = client.post(
        f"/learning-items/{first_item}/pdf-notes",
        json={
            "media_id": first_media,
            "page_number": 1,
            "source_excerpt": None,
            "note_text": "Private note",
        },
        headers=first_headers,
    )
    note_id = created.json()["id"]
    assert client.get(
        f"/learning-items/{first_item}/pdf-notes", headers=second_headers
    ).status_code == 404
    assert client.patch(
        f"/learning-items/{first_item}/pdf-notes/{note_id}",
        json={"source_excerpt": None, "note_text": "Stolen"},
        headers=second_headers,
    ).status_code == 404
    assert client.delete(
        f"/learning-items/{first_item}/pdf-notes/{note_id}",
        headers=second_headers,
    ).status_code == 404
    assert second_item != first_item


def test_pdf_note_validation_rejects_blank_or_oversized_content(
    client,
    registered_user,
    db_session,
) -> None:
    headers = registered_user["headers"]
    item_id, media_id = _create_item_with_pdf(client, headers, db_session)
    blank = client.post(
        f"/learning-items/{item_id}/pdf-notes",
        json={
            "media_id": media_id,
            "page_number": 1,
            "source_excerpt": None,
            "note_text": "   ",
        },
        headers=headers,
    )
    assert blank.status_code == 422
    oversized = client.post(
        f"/learning-items/{item_id}/pdf-notes",
        json={
            "media_id": media_id,
            "page_number": 1,
            "source_excerpt": "x" * 501,
            "note_text": "Valid",
        },
        headers=headers,
    )
    assert oversized.status_code == 422
    assert db_session.scalar(text("SELECT COUNT(*) FROM pdf_notes")) == 0
