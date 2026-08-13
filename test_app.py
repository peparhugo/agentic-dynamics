import sqlite3

import pytest

import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(app, "DATABASE", str(database))
    app.init_db()
    app.app.config.update(TESTING=True)
    return app.app.test_client()


def auth_header(client, username="alice", password="correct horse battery staple"):
    response = client.post("/auth/register", json={"username": username, "password": password})
    assert response.status_code == 201
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def test_create_task_uses_pending_status(client):
    response = client.post("/tasks", json={"title": "Write tests"}, headers=auth_header(client))

    assert response.status_code == 201
    task = response.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]


@pytest.mark.parametrize("payload", [{}, {"title": ""}, {"title": "   "}, {"title": 1}])
def test_create_task_requires_a_title(client, payload):
    response = client.post("/tasks", json=payload, headers=auth_header(client))

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_orders_newest_first(client):
    headers = auth_header(client)
    first = client.post("/tasks", json={"title": "First"}, headers=headers).get_json()
    second = client.post("/tasks", json={"title": "Second"}, headers=headers).get_json()

    response = client.get("/tasks", headers=headers)

    assert response.status_code == 200
    assert [task["id"] for task in response.get_json()] == [second["id"], first["id"]]


def test_get_task_and_missing_task(client):
    headers = auth_header(client)
    task = client.post("/tasks", json={"title": "Read docs"}, headers=headers).get_json()

    response = client.get(f"/tasks/{task['id']}", headers=headers)
    assert response.status_code == 200
    assert response.get_json() == task

    missing = client.get("/tasks/999", headers=headers)
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "task not found"}


def test_update_task_title_and_status(client):
    headers = auth_header(client)
    task = client.post("/tasks", json={"title": "Draft"}, headers=headers).get_json()

    response = client.put(
        f"/tasks/{task['id']}", json={"title": "Published", "status": "done"}, headers=headers
    )

    assert response.status_code == 200
    assert response.get_json() == {**task, "title": "Published", "status": "done"}


def test_update_missing_task_returns_json_error(client):
    response = client.put("/tasks/999", json={"status": "done"}, headers=auth_header(client))

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_schema_is_initialized():
    with app.get_db() as connection:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'tasks'"
        ).fetchone()
    assert table is not None


def test_register_rejects_duplicate_username_and_hashes_password(client, tmp_path):
    assert client.post("/auth/register", json={"username": "alice", "password": "secret"}).status_code == 201
    assert client.post("/auth/register", json={"username": "alice", "password": "other"}).status_code == 409
    with sqlite3.connect(tmp_path / "tasks.db") as connection:
        password_hash = connection.execute("SELECT password_hash FROM users WHERE username = 'alice'").fetchone()[0]
    assert password_hash != "secret"


def test_login_returns_token_and_rejects_invalid_credentials(client):
    auth_header(client)
    assert client.post("/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401


def test_tasks_require_authentication(client):
    for response in (client.get("/tasks"), client.post("/tasks", json={"title": "Nope"}), client.get("/tasks/1"), client.put("/tasks/1", json={"status": "done"})):
        assert response.status_code == 401


def test_users_cannot_access_each_others_tasks(client):
    alice = auth_header(client, "alice")
    bob = auth_header(client, "bob")
    task = client.post("/tasks", json={"title": "Private"}, headers=alice).get_json()
    assert client.get("/tasks", headers=bob).get_json() == []
    assert client.get(f"/tasks/{task['id']}", headers=bob).status_code == 404
    assert client.put(f"/tasks/{task['id']}", json={"status": "done"}, headers=bob).status_code == 404
