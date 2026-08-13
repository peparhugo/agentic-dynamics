import sqlite3

import pytest

import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(app, "DATABASE", str(database))
    app.init_db()
    with app.app.test_client() as client:
        yield client


def register_and_login(client, username="alice", password="secret"):
    response = client.post("/auth/register", json={"username": username, "password": password})
    assert response.status_code == 201
    response = client.post("/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {response.json['token']}"}


def test_create_task_uses_pending_status(client):
    response = client.post("/tasks", json={"title": "Write tests"}, headers=register_and_login(client))

    assert response.status_code == 201
    assert response.json["id"] == 1
    assert response.json["title"] == "Write tests"
    assert response.json["status"] == "pending"
    assert response.json["created_at"]


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": 5}])
def test_create_task_requires_title(client, body):
    response = client.post("/tasks", json=body, headers=register_and_login(client))

    assert response.status_code == 400
    assert response.json == {"error": "title is required"}


def test_list_tasks_returns_newest_first(client):
    headers = register_and_login(client)
    first = client.post("/tasks", json={"title": "First"}, headers=headers).json
    second = client.post("/tasks", json={"title": "Second"}, headers=headers).json

    response = client.get("/tasks", headers=headers)

    assert response.status_code == 200
    assert [task["id"] for task in response.json] == [second["id"], first["id"]]


def test_get_task_and_missing_task(client):
    headers = register_and_login(client)
    task = client.post("/tasks", json={"title": "Fetch me"}, headers=headers).json

    response = client.get(f"/tasks/{task['id']}", headers=headers)
    missing_response = client.get("/tasks/99", headers=headers)

    assert response.status_code == 200
    assert response.json == task
    assert missing_response.status_code == 404
    assert missing_response.json == {"error": "task not found"}


def test_update_task_title_and_status(client):
    headers = register_and_login(client)
    task = client.post("/tasks", json={"title": "Original"}, headers=headers).json

    response = client.put(
        f"/tasks/{task['id']}", json={"title": "Updated", "status": "done"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json == {**task, "title": "Updated", "status": "done"}


def test_completing_task_queues_notification(client, monkeypatch):
    headers = register_and_login(client, "alice@example.com")
    task = client.post("/tasks", json={"title": "Notify me"}, headers=headers).json
    queued = []
    monkeypatch.setattr(app.send_notification_email, "delay", lambda *args: queued.append(args))

    response = client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)

    assert response.status_code == 200
    assert queued == [("alice@example.com", "Notify me")]


def test_recompleting_task_does_not_queue_duplicate_notification(client, monkeypatch):
    headers = register_and_login(client, "alice@example.com")
    task = client.post("/tasks", json={"title": "Notify once"}, headers=headers).json
    queued = []
    monkeypatch.setattr(app.send_notification_email, "delay", lambda *args: queued.append(args))

    client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)
    client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)

    assert queued == [("alice@example.com", "Notify once")]


def test_update_missing_task_returns_json_404(client):
    response = client.put("/tasks/99", json={"status": "done"}, headers=register_and_login(client))

    assert response.status_code == 404
    assert response.json == {"error": "task not found"}


def test_registration_rejects_duplicate_usernames_and_hashes_password(client):
    assert client.post("/auth/register", json={"username": "alice", "password": "secret"}).status_code == 201
    duplicate = client.post("/auth/register", json={"username": "alice", "password": "other"})

    with sqlite3.connect(app.DATABASE) as conn:
        password_hash = conn.execute("SELECT password_hash FROM users WHERE username = 'alice'").fetchone()[0]

    assert duplicate.status_code == 409
    assert password_hash != "secret"


def test_login_returns_token_and_rejects_bad_credentials(client):
    register_and_login(client)

    assert client.post("/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401
    response = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    assert response.status_code == 200
    assert response.json["token"]


def test_tasks_require_valid_bearer_token(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "No auth"}).status_code == 401
    assert client.get("/tasks", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_users_cannot_access_each_others_tasks(client):
    alice_headers = register_and_login(client, "alice")
    bob_headers = register_and_login(client, "bob")
    task = client.post("/tasks", json={"title": "Alice only"}, headers=alice_headers).json

    assert client.get("/tasks", headers=bob_headers).json == []
    assert client.get(f"/tasks/{task['id']}", headers=bob_headers).status_code == 404
    assert client.put(f"/tasks/{task['id']}", json={"status": "done"}, headers=bob_headers).status_code == 404


def test_init_db_migrates_existing_tasks_without_losing_data(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL)")
        conn.execute("INSERT INTO tasks (title, status, created_at) VALUES ('Legacy', 'pending', '2020-01-01')")
    monkeypatch.setattr(app, "DATABASE", str(database))

    app.init_db()

    with sqlite3.connect(database) as conn:
        assert conn.execute("SELECT title, owner_id FROM tasks").fetchone() == ("Legacy", None)
