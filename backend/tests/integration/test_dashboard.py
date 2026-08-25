def test_dashboard_is_scoped_to_current_user(client, registered_user) -> None:
    headers = registered_user["headers"]
    response = client.get("/dashboard/summary", headers=headers)
    assert response.status_code == 200
    assert response.json() == {
        "username": "atul",
        "total_items": 0,
        "total_labels": 0,
        "login_streak": 1,
    }
