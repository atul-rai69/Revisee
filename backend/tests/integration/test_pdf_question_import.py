from sqlalchemy import text


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


def _item(client, headers, title: str) -> int:
    response = client.post(
        "/learning-items",
        data={"title": title, "description_text": "Source notes", "labels": "[]"},
        headers=headers,
    )
    assert response.status_code == 200
    item_id = next(
        entry["id"]
        for entry in client.get("/dashboard/learning-items-summary", headers=headers).json()["data"]
        if entry["title"] == title
    )
    return item_id


def _draft():
    return {
        "question": "What is supported by the supplied passage?",
        "options": {"A": "Alpha", "B": "Beta", "C": "Gamma", "D": "Delta"},
        "correct_option": "A",
        "explanation": "The passage states Grounded evidence.",
        "difficulty": 2,
        "expected_time_seconds": 30,
        "source_page": 1,
        "source_excerpt": "Grounded evidence",
        "confidence": 0.9,
        "validation_issues": [],
    }


def test_review_first_generation_import_and_duplicate_reporting(client, db_session) -> None:
    headers = _register(client, "pdf-import-owner")
    source_id = _item(client, headers, "PDF source")
    destination_id = _item(client, headers, "Destination")
    source_pages = [{"page_number": 1, "text": "Grounded evidence appears here."}]

    generated = client.post(
        f"/learning-items/{source_id}/pdf-question-drafts/generate",
        json={
            "source_filename": "biology-question-paper.pdf",
            "mode": "GENERATE",
            "source_pages": source_pages,
            "question_count": 1,
            "difficulty": 2,
            "focus_instructions": None,
            "generation_source": "REVISEE",
            "credential_id": None,
        },
        headers=headers,
    )
    assert generated.status_code == 200
    assert generated.json()["returned_count"] == 1
    assert db_session.scalar(
        text("SELECT COUNT(*) FROM questions WHERE learning_item_id = :item_id"),
        {"item_id": destination_id},
    ) == 1  # the normal learning-item creation question only

    payload = {
        "source_filename": "biology-question-paper.pdf",
        "destination_learning_item_id": destination_id,
        "source_pages": source_pages,
        "questions": [_draft()],
    }
    imported = client.post(
        f"/learning-items/{source_id}/pdf-questions/import",
        json=payload,
        headers=headers,
    )
    repeated = client.post(
        f"/learning-items/{source_id}/pdf-questions/import",
        json=payload,
        headers=headers,
    )
    assert imported.status_code == 200
    assert imported.json()["inserted_count"] == 1
    assert repeated.status_code == 200
    assert repeated.json()["inserted_count"] == 0
    assert repeated.json()["duplicate_count"] == 1


def test_source_destination_and_byok_ownership_are_concealed(client, db_session) -> None:
    owner = _register(client, "pdf-private-owner")
    other = _register(client, "pdf-private-other")
    source_id = _item(client, owner, "Private source")
    other_source_id = _item(client, other, "Other source")
    pages = [{"page_number": 1, "text": "Grounded evidence appears here."}]

    cross_source = client.post(
        f"/learning-items/{source_id}/pdf-question-drafts/generate",
        json={"source_filename": "private.pdf", "mode": "GENERATE", "source_pages": pages, "question_count": 1, "difficulty": 2, "focus_instructions": None, "generation_source": "REVISEE", "credential_id": None},
        headers=other,
    )
    cross_destination = client.post(
        f"/learning-items/{other_source_id}/pdf-questions/import",
        json={"source_filename": "other.pdf", "destination_learning_item_id": source_id, "source_pages": pages, "questions": [_draft()]},
        headers=other,
    )
    credential = client.post(
        "/ai-credentials",
        json={"provider": "GEMINI", "name": "Owner key", "api_key": "owner-key-123456789", "make_default": True},
        headers=owner,
    ).json()
    foreign_key = client.post(
        f"/learning-items/{other_source_id}/pdf-question-drafts/generate",
        json={"source_filename": "other.pdf", "mode": "GENERATE", "source_pages": pages, "question_count": 1, "difficulty": 2, "focus_instructions": None, "generation_source": "PERSONAL", "credential_id": credential["id"]},
        headers=other,
    )

    assert cross_source.status_code == 404
    assert cross_destination.status_code == 404
    assert foreign_key.status_code == 404
