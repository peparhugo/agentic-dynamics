def test_create_category(client, auth_headers):
    resp = client.post(
        "/api/categories",
        json={"name": "Personal", "description": "Personal stuff"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["name"] == "Personal"
    assert body["description"] == "Personal stuff"
    assert body["id"] is not None


def test_create_category_requires_auth(client):
    resp = client.post("/api/categories", json={"name": "Personal"})
    assert resp.status_code == 401


def test_create_category_missing_name(client, auth_headers):
    resp = client.post("/api/categories", json={"description": "x"}, headers=auth_headers)
    assert resp.status_code == 400


def test_create_category_duplicate(client, auth_headers):
    client.post("/api/categories", json={"name": "Work"}, headers=auth_headers)
    resp = client.post("/api/categories", json={"name": "Work"}, headers=auth_headers)
    assert resp.status_code == 409


def test_list_categories(client, auth_headers):
    client.post("/api/categories", json={"name": "Alpha"}, headers=auth_headers)
    client.post("/api/categories", json={"name": "Beta"}, headers=auth_headers)
    resp = client.get("/api/categories", headers=auth_headers)
    assert resp.status_code == 200
    names = [c["name"] for c in resp.get_json()]
    assert names == ["Alpha", "Beta"]


def test_get_category(client, auth_headers, category_id):
    resp = client.get(f"/api/categories/{category_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["id"] == category_id


def test_get_category_not_found(client, auth_headers):
    resp = client.get("/api/categories/9999", headers=auth_headers)
    assert resp.status_code == 404


def test_update_category(client, auth_headers, category_id):
    resp = client.put(
        f"/api/categories/{category_id}",
        json={"name": "Work Updated", "description": "new desc"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Work Updated"
    assert resp.get_json()["description"] == "new desc"


def test_update_category_duplicate_name(client, auth_headers):
    client.post("/api/categories", json={"name": "One"}, headers=auth_headers)
    c2 = client.post("/api/categories", json={"name": "Two"}, headers=auth_headers).get_json()
    resp = client.put(
        f"/api/categories/{c2['id']}", json={"name": "One"}, headers=auth_headers
    )
    assert resp.status_code == 409


def test_delete_category(client, auth_headers, category_id):
    resp = client.delete(f"/api/categories/{category_id}", headers=auth_headers)
    assert resp.status_code == 200
    resp2 = client.get(f"/api/categories/{category_id}", headers=auth_headers)
    assert resp2.status_code == 404


def test_delete_category_not_found(client, auth_headers):
    resp = client.delete("/api/categories/9999", headers=auth_headers)
    assert resp.status_code == 404


def test_delete_category_with_tasks(client, auth_headers, category_id):
    client.post(
        "/api/tasks",
        json={"title": "Task with category", "category_id": category_id},
        headers=auth_headers,
    )
    resp = client.delete(f"/api/categories/{category_id}", headers=auth_headers)
    assert resp.status_code == 409
