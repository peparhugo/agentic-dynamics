def auth_header(client, username="bob"):
    res = client.post("/api/v1/auth/login", json={"username": username, "password": "pw"})
    token = res.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_get_update_delete_item(client):
    headers = auth_header(client)

    # Create
    res = client.post("/api/v1/items", json={"name": "Item1", "description": "desc"}, headers=headers)
    assert res.status_code == 201
    item = res.get_json()
    assert item["name"] == "Item1"
    item_id = item["id"]

    # Get
    res2 = client.get(f"/api/v1/items/{item_id}", headers=headers)
    assert res2.status_code == 200
    assert res2.get_json()["id"] == item_id

    # Update
    res3 = client.patch(f"/api/v1/items/{item_id}", json={"name": "Updated"}, headers=headers)
    assert res3.status_code == 200
    assert res3.get_json()["name"] == "Updated"

    # List with pagination
    res4 = client.get("/api/v1/items?page=1&per_page=10", headers=headers)
    assert res4.status_code == 200
    payload = res4.get_json()
    assert "data" in payload and "meta" in payload
    assert payload["meta"]["page"] == 1

    # Delete
    res5 = client.delete(f"/api/v1/items/{item_id}", headers=headers)
    assert res5.status_code == 204

    # Get after delete
    res6 = client.get(f"/api/v1/items/{item_id}", headers=headers)
    assert res6.status_code == 404


def test_validation_errors(client):
    headers = auth_header(client)
    # Missing name should 422
    res = client.post("/api/v1/items", json={"description": "x"}, headers=headers)
    assert res.status_code == 422
    body = res.get_json()
    assert body["error"] == "validation_error"
