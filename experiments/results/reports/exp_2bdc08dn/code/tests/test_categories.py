def test_create_category(client, auth_headers):
    headers = auth_headers()
    resp = client.post("/api/categories", json={"name": "Work"}, headers=headers)
    body = resp.get_json()
    assert resp.status_code == 201
    assert body["category"]["name"] == "Work"
    assert "id" in body["category"]


def test_create_category_missing_name(client, auth_headers):
    headers = auth_headers()
    resp = client.post("/api/categories", json={}, headers=headers)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "name is required"


def test_create_duplicate_category(client, auth_headers):
    headers = auth_headers()
    assert client.post("/api/categories", json={"name": "Work"}, headers=headers).status_code == 201
    resp = client.post("/api/categories", json={"name": "Work"}, headers=headers)
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "category already exists"


def test_create_duplicate_category_case_sensitive(client, auth_headers):
    headers = auth_headers()
    client.post("/api/categories", json={"name": "Work"}, headers=headers)
    resp = client.post("/api/categories", json={"name": "work"}, headers=headers)
    assert resp.status_code == 201


def test_list_categories(client, auth_headers):
    headers = auth_headers()
    client.post("/api/categories", json={"name": "Work"}, headers=headers)
    client.post("/api/categories", json={"name": "Personal"}, headers=headers)
    resp = client.get("/api/categories", headers=headers)
    assert resp.status_code == 200
    names = [c["name"] for c in resp.get_json()["categories"]]
    assert names == ["Personal", "Work"]


def test_delete_category(client, auth_headers):
    headers = auth_headers()
    created = client.post(
        "/api/categories", json={"name": "Work"}, headers=headers
    ).get_json()["category"]
    resp = client.delete(f"/api/categories/{created['id']}", headers=headers)
    assert resp.status_code == 204
    remaining = client.get("/api/categories", headers=headers).get_json()["categories"]
    assert remaining == []


def test_delete_category_not_found(client, auth_headers):
    headers = auth_headers()
    resp = client.delete("/api/categories/999", headers=headers)
    assert resp.status_code == 404


def test_categories_are_user_scoped(client, auth_headers):
    alice_headers = auth_headers("alice")
    bob_headers = auth_headers("bob")
    created = client.post(
        "/api/categories", json={"name": "Secret"}, headers=alice_headers
    ).get_json()["category"]

    resp = client.delete(f"/api/categories/{created['id']}", headers=bob_headers)
    assert resp.status_code == 404

    bob_list = client.get("/api/categories", headers=bob_headers).get_json()["categories"]
    assert bob_list == []


def test_categories_require_auth(client):
    resp = client.post("/api/categories", json={"name": "Work"})
    assert resp.status_code == 401
    assert client.get("/api/categories").status_code == 401
