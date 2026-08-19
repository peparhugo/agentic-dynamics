def test_list_categories_empty(auth_client):
    response = auth_client.get("/api/categories")
    assert response.status_code == 200
    assert response.get_json() == {"items": [], "total": 0}


def test_create_category(auth_client):
    response = auth_client.post("/api/categories", json={"name": "personal"})
    assert response.status_code == 201
    assert response.get_json()["name"] == "personal"


def test_create_category_missing_name(auth_client):
    response = auth_client.post("/api/categories", json={})
    assert response.status_code == 400


def test_create_duplicate_category(auth_client):
    auth_client.post("/api/categories", json={"name": "shopping"})
    response = auth_client.post("/api/categories", json={"name": "shopping"})
    assert response.status_code == 409


def test_list_categories_sorted(auth_client):
    for name in ("zebra", "alpha", "mid"):
        auth_client.post("/api/categories", json={"name": name})
    response = auth_client.get("/api/categories")
    names = [item["name"] for item in response.get_json()["items"]]
    assert names == ["alpha", "mid", "zebra"]


def test_categories_require_auth(client):
    assert client.get("/api/categories").status_code == 401


def test_create_task_with_category(auth_client):
    auth_client.post("/api/categories", json={"name": "work"})
    response = auth_client.post("/api/tasks", json={"title": "Work task", "category": "work"})
    assert response.status_code == 201
    assert response.get_json()["category"] == "work"


def test_delete_category_detaches_tasks(auth_client, create_task):
    auth_client.post("/api/categories", json={"name": "temporary"})
    task = create_task({"title": "Temp", "category": "temporary"})
    response = auth_client.delete("/api/categories/1")
    assert response.status_code == 204
    fetched = auth_client.get(f"/api/tasks/{task['id']}").get_json()
    assert fetched["category"] is None
    assert auth_client.get("/api/categories").get_json()["total"] == 0


def test_delete_missing_category(auth_client):
    response = auth_client.delete("/api/categories/99999")
    assert response.status_code == 404
