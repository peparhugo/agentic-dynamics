from task_api.db import get_db


def test_category_lifecycle(client, auth_headers):
    created = client.post("/api/categories", json={"name": "Work"}, headers=auth_headers)
    assert created.status_code == 201
    category_id = created.get_json()["category"]["id"]

    listed = client.get("/api/categories", headers=auth_headers)
    assert listed.get_json()["categories"][0]["task_count"] == 0

    updated = client.patch(
        f"/api/categories/{category_id}", json={"name": "Personal"}, headers=auth_headers
    )
    assert updated.status_code == 200
    assert updated.get_json()["category"]["name"] == "Personal"

    assert client.delete(f"/api/categories/{category_id}", headers=auth_headers).status_code == 204
    assert client.delete(f"/api/categories/{category_id}", headers=auth_headers).status_code == 404


def test_category_validation_and_duplicates(client, auth_headers):
    assert client.post("/api/categories", json={"name": ""}, headers=auth_headers).status_code == 400
    assert client.post("/api/categories", json={"name": "Work"}, headers=auth_headers).status_code == 201
    assert client.post("/api/categories", json={"name": "work"}, headers=auth_headers).status_code == 409


def test_deleting_category_unsets_task_category(client, app, auth_headers, category):
    task = client.post(
        "/api/tasks", json={"title": "Categorized", "category_id": category["id"]}, headers=auth_headers
    ).get_json()["task"]
    client.delete(f"/api/categories/{category['id']}", headers=auth_headers)
    response = client.get(f"/api/tasks/{task['id']}", headers=auth_headers)
    assert response.get_json()["task"]["category_id"] is None
    with app.app_context():
        assert get_db().execute("PRAGMA foreign_keys").fetchone()[0] == 1
