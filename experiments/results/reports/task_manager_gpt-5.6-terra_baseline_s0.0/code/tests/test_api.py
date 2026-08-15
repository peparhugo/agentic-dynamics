import sqlite3

import pytest

from app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "tasks.sqlite"), "SECRET_KEY": "test-secret"})
    return app.test_client()


def register(client, username="alice", password="secure-password"):
    return client.post("/auth/register", json={"username": username, "password": password})


def auth(client, username="alice", password="secure-password"):
    register(client, username, password)
    response = client.post("/auth/login", json={"username": username, "password": password})
    return {"Authorization": "Bearer " + response.json["token"]}


def test_registration_and_login(client):
    response = register(client)
    assert response.status_code == 201
    assert response.json["user"]["username"] == "alice"
    assert register(client).status_code == 409
    assert client.post("/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401
    response = client.post("/auth/login", json={"username": "alice", "password": "secure-password"})
    assert response.status_code == 200 and response.json["token"]


def test_authentication_is_required(client):
    assert client.get("/tasks").status_code == 401
    assert client.get("/tasks", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_category_crud(client):
    headers = auth(client)
    created = client.post("/categories", headers=headers, json={"name": "Work"})
    assert created.status_code == 201
    category_id = created.json["category"]["id"]
    assert client.post("/categories", headers=headers, json={"name": "Work"}).status_code == 409
    assert len(client.get("/categories", headers=headers).json["categories"]) == 1
    assert client.patch(f"/categories/{category_id}", headers=headers, json={"name": "Office"}).json["category"]["name"] == "Office"
    assert client.delete(f"/categories/{category_id}", headers=headers).status_code == 204


def test_task_crud_with_all_fields(client):
    headers = auth(client)
    category = client.post("/categories", headers=headers, json={"name": "Work"}).json["category"]
    created = client.post("/tasks", headers=headers, json={"title": "Ship API", "description": "Finish it", "category_id": category["id"], "priority": "high", "status": "in_progress", "due_date": "2026-12-30"})
    assert created.status_code == 201
    task = created.json["task"]
    assert task["category_name"] == "Work" and task["priority"] == "high"
    updated = client.patch(f"/tasks/{task['id']}", headers=headers, json={"status": "done", "due_date": None})
    assert updated.status_code == 200 and updated.json["task"]["status"] == "done"
    assert client.get(f"/tasks/{task['id']}", headers=headers).status_code == 200
    assert client.delete(f"/tasks/{task['id']}", headers=headers).status_code == 204
    assert client.get(f"/tasks/{task['id']}", headers=headers).status_code == 404


def test_task_validation(client):
    headers = auth(client)
    assert client.post("/tasks", headers=headers, json={}).status_code == 400
    assert client.post("/tasks", headers=headers, json={"title": "x", "priority": "urgent"}).status_code == 400
    assert client.post("/tasks", headers=headers, json={"title": "x", "due_date": "tomorrow"}).status_code == 400
    assert client.post("/tasks", headers=headers, json={"title": "x", "category_id": 999}).status_code == 400


def test_assignment_and_access_control(client):
    alice = auth(client, "alice")
    bob = auth(client, "bob")
    users = client.get("/users", headers=alice).json["users"]
    bob_id = next(user["id"] for user in users if user["username"] == "bob")
    task_id = client.post("/tasks", headers=alice, json={"title": "Review", "assignee_id": bob_id}).json["task"]["id"]
    assert client.get(f"/tasks/{task_id}", headers=bob).status_code == 200
    assert client.patch(f"/tasks/{task_id}", headers=bob, json={"status": "done"}).status_code == 404
    assert client.delete(f"/tasks/{task_id}", headers=bob).status_code == 404


def test_pagination_search_and_filters(client):
    headers = auth(client)
    work = client.post("/categories", headers=headers, json={"name": "Work"}).json["category"]
    for title, status, priority, category_id in [("alpha report", "todo", "high", work["id"]), ("beta note", "done", "low", None), ("alpha followup", "todo", "high", work["id"])]:
        assert client.post("/tasks", headers=headers, json={"title": title, "status": status, "priority": priority, "category_id": category_id}).status_code == 201
    response = client.get(f"/tasks?search=alpha&status=todo&priority=high&category_id={work['id']}&per_page=1", headers=headers)
    assert response.status_code == 200
    assert response.json["pagination"] == {"page": 1, "per_page": 1, "total": 2, "pages": 2}
    assert len(response.json["tasks"]) == 1
    assert client.get("/tasks?page=0", headers=headers).status_code == 400


def test_migration_records_version(client, tmp_path):
    connection = sqlite3.connect(tmp_path / "tasks.sqlite")
    assert connection.execute("SELECT version FROM schema_migrations").fetchone()[0] == "001_initial.sql"
