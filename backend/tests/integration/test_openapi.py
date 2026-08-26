def test_legacy_openapi_paths_are_preserved(client) -> None:
    schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {
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
    operation_count = sum(
        method in {"get", "post", "patch", "delete"}
        for path in schema["paths"].values()
        for method in path
    )
    assert operation_count == 14
