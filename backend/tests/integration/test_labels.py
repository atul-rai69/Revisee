def test_label_crud_contract(client, registered_user) -> None:
    headers = registered_user["headers"]
    created = client.post("/labels", json={"label_name": "Biology"}, headers=headers)
    assert created.status_code == 200
    label = created.json()["label"]
    assert label["label_name"] == "Biology"

    listed = client.get("/labels", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == label["id"]

    updated = client.patch(
        "/labels",
        json={"id": label["id"], "label_name": "Cell Biology"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["label"]["label_name"] == "Cell Biology"
