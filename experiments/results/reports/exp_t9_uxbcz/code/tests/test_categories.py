def test_create_category(client, auth_headers):
    resp = client.post(
        "/api/categories",
        json={"name": "Work", "description": "work stuff"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["name"] == "Work"
    assert data["description"] == "work stuff"


def test_create_category_requires_auth(client):
    resp = client.post("/api/categories", json={"name": "Work"})
    assert resp.status_code == 401


def test_create_category_missing_name(client, auth_headers):
    resp = client.post("/api/categories", json={}, headers=auth_headers)
    assert resp.status_code == 400


def test_create_duplicate_category(client, auth_headers):
    client.post("/api/categories", json={"name": "Work"}, headers=auth_headers)
    resp = client.post("/api/categories", json={"name": "Work"}, headers=auth_headers)
    assert resp.status_code == 409


def test_list_categories(client, auth_headers):
    client.post("/api/categories", json={"name": "Work"}, headers=auth_headers)
    client.post("/api/categories", json={"name": "Home"}, headers=auth_headers)
    resp = client.get("/api/categories", headers=auth_headers)
    assert resp.status_code == 200
    names = [c["name"] for c in resp.get_json()["categories"]]
    assert names == ["Home", "Work"]


def test_get_category(client, auth_headers, category):
    resp = client.get(f"/api/categories/{category['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Work"


def test_get_category_not_found(client, auth_headers):
    resp = client.get("/api/categories/9999", headers=auth_headers)
    assert resp.status_code == 404


def test_update_category(client, auth_headers, category):
    resp = client.put(
        f"/api/categories/{category['id']}",
        json={"name": "Personal", "description": "updated"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["name"] == "Personal"
    assert data["description"] == "updated"


def test_update_category_not_found(client, auth_headers):
    resp = client.put("/api/categories/9999", json={"name": "X"}, headers=auth_headers)
    assert resp.status_code == 404


def test_delete_category_detaches_tasks(client, auth_headers, category):
    from app.extensions import db
    from app.models import Task

    client.post(
        "/api/tasks",
        json={"title": "Task A", "category_id": category["id"]},
        headers=auth_headers,
    )
    resp = client.delete(f"/api/categories/{category['id']}", headers=auth_headers)
    assert resp.status_code == 200

    task = Task.query.first()
    assert task.category_id is None


def test_delete_category_not_found(client, auth_headers):
    resp = client.delete("/api/categories/9999", headers=auth_headers)
    assert resp.status_code == 404
