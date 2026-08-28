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
        "/revision-sessions/{session_id}/submit",
        "/revision-sessions/{session_id}/result",
        "/weak-areas",
    }
    current_paths = set(schema["paths"])

    assert legacy_paths <= current_paths
    assert current_paths == legacy_paths | approved_additions
    assert "post" in schema["paths"]["/revision-sessions/{session_id}/submit"]
    assert "get" in schema["paths"]["/revision-sessions/{session_id}/result"]
    assert "get" in schema["paths"]["/weak-areas"]

    operation_count = sum(
        method in {"get", "post", "patch", "delete"}
        for path in schema["paths"].values()
        for method in path
    )
    assert operation_count == 17
