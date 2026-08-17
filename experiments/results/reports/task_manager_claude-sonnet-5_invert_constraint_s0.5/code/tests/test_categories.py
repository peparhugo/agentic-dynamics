def create_category(client, headers, name="Work", description="Work related tasks"):
    return client.post(
        "/api/categories", json={"name": name, "description": description}, headers=headers
    )


def test_create_category_requires_auth(client):
    resp = client.post("/api/categories", json={"name": "Work"})
    assert resp.status_code == 401


def test_create_category(client, auth_headers):
    resp = create_category(client, auth_headers)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["name"] == "Work"
    assert body["description"] == "Work related tasks"


def test_create_category_missing_name(client, auth_headers):
    resp = client.post("/api/categories", json={}, headers=auth_headers)
    assert resp.status_code == 400


def test_create_duplicate_category(client, auth_headers):
    create_category(client, auth_headers)
    resp = create_category(client, auth_headers)
    assert resp.status_code == 409


def test_list_categories(client, auth_headers):
    create_category(client, auth_headers, name="Work")
    create_category(client, auth_headers, name="Home")
    resp = client.get("/api/categories", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total"] == 2
    names = sorted(item["name"] for item in body["items"])
    assert names == ["Home", "Work"]


def test_get_category(client, auth_headers):
    created = create_category(client, auth_headers).get_json()
    resp = client.get(f"/api/categories/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["id"] == created["id"]


def test_get_missing_category(client, auth_headers):
    resp = client.get("/api/categories/9999", headers=auth_headers)
    assert resp.status_code == 404


def test_update_category(client, auth_headers):
    created = create_category(client, auth_headers).get_json()
    resp = client.put(
        f"/api/categories/{created['id']}",
        json={"name": "Personal", "description": "Updated"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["name"] == "Personal"
    assert body["description"] == "Updated"


def test_update_category_duplicate_name(client, auth_headers):
    create_category(client, auth_headers, name="Work")
    other = create_category(client, auth_headers, name="Home").get_json()
    resp = client.put(
        f"/api/categories/{other['id']}", json={"name": "Work"}, headers=auth_headers
    )
    assert resp.status_code == 409


def test_delete_category(client, auth_headers):
    created = create_category(client, auth_headers).get_json()
    resp = client.delete(f"/api/categories/{created['id']}", headers=auth_headers)
    assert resp.status_code == 204

    resp = client.get(f"/api/categories/{created['id']}", headers=auth_headers)
    assert resp.status_code == 404


def test_delete_category_nulls_task_category(client, auth_headers):
    category = create_category(client, auth_headers).get_json()
    task_resp = client.post(
        "/api/tasks",
        json={"title": "Buy groceries", "category_id": category["id"]},
        headers=auth_headers,
    )
    task = task_resp.get_json()

    client.delete(f"/api/categories/{category['id']}", headers=auth_headers)

    resp = client.get(f"/api/tasks/{task['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["category_id"] is None
