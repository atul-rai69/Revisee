def test_legacy_openapi_paths_are_preserved(client) -> None:
    schema = client.get("/openapi.json").json()
    legacy_paths = {
        "/register",
        "/login",
        "/logout",
        "/labels",
        "/learning-items",
        "/learning-item/{item_id}",
        "/dashboard/summary",
        "/dashboard/learning-items-summary",
        "/generate",
        "/revision-sessions",
        "/revision-sessions/{session_id}",
    }
    approved_additions = {
        "/health",
        "/revision-sessions/{session_id}/submit",
        "/revision-sessions/{session_id}/result",
        "/weak-areas",
        "/revision-sessions/smart-readiness",
        "/mastery/analytics",
        "/learning-items/{item_id}/questions",
        "/analytics/revision-activity",
        "/ai-credentials",
        "/ai-credentials/{credential_id}",
        "/ai-credentials/{credential_id}/default",
        "/learning-items/{item_id}/generated-questions",
        "/learning-items/{item_id}/pdf-notes",
        "/learning-items/{item_id}/pdf-notes/{note_id}",
    }
    current_paths = set(schema["paths"])

    assert legacy_paths <= current_paths
    assert current_paths == legacy_paths | approved_additions
    assert "post" in schema["paths"]["/revision-sessions/{session_id}/submit"]
    assert "get" in schema["paths"]["/revision-sessions/{session_id}/result"]
    assert "get" in schema["paths"]["/weak-areas"]
    assert "get" in schema["paths"]["/revision-sessions"]
    assert "get" in schema["paths"]["/revision-sessions/smart-readiness"]
    assert "get" in schema["paths"]["/mastery/analytics"]
    assert "post" in schema["paths"]["/learning-items/{item_id}/questions"]
    assert "get" in schema["paths"]["/analytics/revision-activity"]
    assert {"get", "post"} <= set(schema["paths"]["/ai-credentials"])
    assert {"patch", "delete"} <= set(schema["paths"]["/ai-credentials/{credential_id}"])
    assert "put" in schema["paths"]["/ai-credentials/{credential_id}/default"]
    assert "post" in schema["paths"]["/learning-items/{item_id}/generated-questions"]
    assert {"get", "post"} <= set(
        schema["paths"]["/learning-items/{item_id}/pdf-notes"]
    )
    assert {"patch", "delete"} <= set(
        schema["paths"]["/learning-items/{item_id}/pdf-notes/{note_id}"]
    )

    operation_count = sum(
        method in {"get", "post", "put", "patch", "delete"}
        for path in schema["paths"].values()
        for method in path
    )
    assert operation_count == 33


def test_health_endpoint_is_public_and_minimal(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_registration_openapi_contract_uses_json_body(client) -> None:
    operation = client.get("/openapi.json").json()["paths"]["/register"]["post"]
    assert "application/json" in operation["requestBody"]["content"]
    query_parameters = [
        parameter["name"]
        for parameter in operation.get("parameters", [])
        if parameter.get("in") == "query"
    ]
    assert not {"username", "email", "password"}.intersection(query_parameters)
