import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_current_user
from src.db.session import get_db
from src.main import app
from src.modules.auth.models import User
from src.modules.mastery.schemas import RevisionAnalyticsResponse
from src.modules.mastery.service import RevisionAnalyticsService


def _empty_response(session_limit: int) -> RevisionAnalyticsResponse:
    return RevisionAnalyticsResponse(
        completed_session_count=0,
        activity=[],
        requested_session_limit=session_limit,
        sessions_used=0,
        measured_learning_item_count=0,
        weak_area_ready=False,
        minimum_attempts=3,
        topic_attribution="CURRENT_LEARNING_ITEM_TOPICS",
        attribution_note="No completed sessions are available.",
        topic_practice=[],
    )


@pytest.mark.parametrize("session_limit", [7, 30, 50])
def test_authenticated_revision_activity_accepts_supported_query_values(
    monkeypatch, session_limit: int
) -> None:
    received: list[tuple[int, int]] = []

    def fake_get(
        _service: RevisionAnalyticsService, user_id: int, requested_limit: int
    ) -> RevisionAnalyticsResponse:
        received.append((user_id, requested_limit))
        return _empty_response(requested_limit)

    monkeypatch.setattr(RevisionAnalyticsService, "get", fake_get)
    app.dependency_overrides[get_current_user] = lambda: User(
        id=41,
        username="contract-user",
        email="contract@example.test",
        password_hash="unused",
    )
    app.dependency_overrides[get_db] = lambda: None
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                f"/analytics/revision-activity?session_limit={session_limit}",
                headers={"Authorization": "Bearer dependency-isolated-test"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["requested_session_limit"] == session_limit
    assert response.json()["completed_session_count"] == 0
    assert received == [(41, session_limit)]


def test_revision_activity_rejects_unsupported_query_value_without_service_call(
    monkeypatch,
) -> None:
    service_called = False

    def fake_get(*_args, **_kwargs) -> RevisionAnalyticsResponse:
        nonlocal service_called
        service_called = True
        return _empty_response(30)

    monkeypatch.setattr(RevisionAnalyticsService, "get", fake_get)
    app.dependency_overrides[get_current_user] = lambda: User(
        id=41,
        username="contract-user",
        email="contract@example.test",
        password_hash="unused",
    )
    app.dependency_overrides[get_db] = lambda: None
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                "/analytics/revision-activity?session_limit=8",
                headers={"Authorization": "Bearer dependency-isolated-test"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["detail"] == [
        {
            "type": "enum",
            "loc": ["query", "session_limit"],
            "msg": "Input should be 7, 30 or 50",
            "input": "8",
            "ctx": {"expected": "7, 30 or 50"},
        }
    ]
    assert service_called is False


def test_revision_activity_openapi_exposes_supported_integer_enum() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        schema = client.get("/openapi.json").json()

    operation = schema["paths"]["/analytics/revision-activity"]["get"]
    parameter = next(
        item for item in operation["parameters"] if item["name"] == "session_limit"
    )
    enum_schema = schema["components"]["schemas"]["RevisionSessionLimit"]

    assert parameter["in"] == "query"
    assert parameter["required"] is False
    assert parameter["schema"]["default"] == 30
    assert enum_schema["type"] == "integer"
    assert enum_schema["enum"] == [7, 30, 50]
