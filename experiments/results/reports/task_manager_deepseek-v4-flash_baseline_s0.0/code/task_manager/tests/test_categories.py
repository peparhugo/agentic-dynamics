def test_list_categories_empty(client, user_token):
    token, headers = user_token()
    response = client.get("/api/categories", headers=headers)
    assert response.status_code == 200
    assert response.get_json()["items"] == []
    assert response.get_json()["total"] == 0


def test_create_and_get_category(client, user_token):
    token, headers = user_token()
    response = client.post("/api/categories", json={"name": "Finance"}, headers=headers)
    assert response.status_code == 201
    body = response.get_json()
    assert body["name"] == "Finance"

    category_id = body["id"]
    response = client.get(f"/api/categories/{category_id}", headers=headers)
    assert response.status_code == 200
    assert response.get_json()["name"] == "Finance"

    response = client.get("/api/categories/9999", headers=headers)
    assert response.status_code == 404


def test_create_category_validation(client, user_token):
    token, headers = user_token()
    response = client.post("/api/categories", json={}, headers=headers)
    assert response.status_code == 400
    assert response.get_json()["error"] == "name is required"

    response = client.post("/api/categories", json={"name": ""}, headers=headers)
    assert response.status_code == 400

    response = client.post("/api/categories", json={"name": "n" * 81}, headers=headers)
    assert response.status_code == 400


def test_duplicate_category_name(client, user_token):
    token, headers = user_token()
    client.post("/api/categories", json={"name": "Engineering"}, headers=headers)
    response = client.post("/api/categories", json={"name": "engineering"}, headers=headers)
    assert response.status_code == 409
    assert response.get_json()["error"] == "category already exists"


def test_list_categories_sorted(client, user_token):
    token, headers = user_token()
    client.post("/api/categories", json={"name": "Zebra"}, headers=headers)
    client.post("/api/categories", json={"name": "Alpha"}, headers=headers)
    response = client.get("/api/categories", headers=headers)
    names = [c["name"] for c in response.get_json()["items"]]
    assert names == ["Alpha", "Zebra"]


def test_update_category_requires_admin(client, user_token, register_user):
    token, headers = user_token()
    category = client.post(
        "/api/categories", json={"name": "Finance"}, headers=headers
    ).get_json()

    other = register_user(username="bob", email="bob@example.com")
    other_headers = {"Authorization": f"Bearer {other['token']}"}
    assert client.put(
        f"/api/categories/{category['id']}", json={"name": "Hacked"}, headers=other_headers
    ).status_code == 403


def test_update_category_as_admin(client, user_token, register_user):
    token, headers = user_token()
    category = client.post(
        "/api/categories", json={"name": "Finance"}, headers=headers
    ).get_json()

    admin = register_user(username="root", email="root@example.com", role="admin")
    admin_headers = {"Authorization": f"Bearer {admin['token']}"}

    response = client.put(
        f"/api/categories/{category['id']}",
        json={"name": "Accounting", "description": "Ledgers"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["name"] == "Accounting"
    assert body["description"] == "Ledgers"

    response = client.put(
        f"/api/categories/{category['id']}", json={"name": "accounting"}, headers=admin_headers
    )
    assert response.status_code == 409

    response = client.put(
        f"/api/categories/{category['id']}", json={"name": ""}, headers=admin_headers
    )
    assert response.status_code == 400


def test_delete_category_detaches_tasks(client, user_token, register_user):
    token, headers = user_token()
    category = client.post(
        "/api/categories", json={"name": "Temp"}, headers=headers
    ).get_json()

    task_response = client.post(
        "/api/tasks",
        json={"title": "Do work", "category_id": category["id"]},
        headers=headers,
    )
    assert task_response.status_code == 201
    task = task_response.get_json()
    assert task["category"]["id"] == category["id"]

    admin = register_user(username="root", email="root@example.com", role="admin")
    admin_headers = {"Authorization": f"Bearer {admin['token']}"}
    response = client.delete(f"/api/categories/{category['id']}", headers=admin_headers)
    assert response.status_code == 204

    task_after = client.get(f"/api/tasks/{task['id']}", headers=headers).get_json()
    assert task_after["category"] is None


def test_delete_category_requires_admin(client, user_token, register_user):
    token, headers = user_token()
    category = client.post(
        "/api/categories", json={"name": "Keep"}, headers=headers
    ).get_json()

    admin = register_user(username="root", email="root@example.com", role="admin")
    admin_headers = {"Authorization": f"Bearer {admin['token']}"}
    assert client.delete(f"/api/categories/{category['id']}", headers=admin_headers).status_code == 204
    assert client.delete(f"/api/categories/{category['id']}", headers=admin_headers).status_code == 404


def test_categories_require_auth(client):
    assert client.get("/api/categories").status_code == 401
    assert client.post("/api/categories", json={"name": "x"}).status_code == 401


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_unknown_route_returns_json_404(client, user_token):
    token, headers = user_token()
    response = client.get("/api/does-not-exist", headers=headers)
    assert response.status_code == 404
    assert response.get_json()["error"] == "Resource not found"
