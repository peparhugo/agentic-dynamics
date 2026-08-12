import sqlite3

import pytest

from app import app, limiter
from celery_config import send_notification_email


@pytest.fixture
def client(tmp_path):
    app.config.update(
        TESTING=True,
        DATABASE=str(tmp_path / "tasks.db"),
        JWT_SECRET="test-secret",
        JWT_EXPIRATION_SECONDS=3600,
    )
    limiter.reset()
    return app.test_client()


def register_and_login(client, username):
    assert client.post("/auth/register", json={"username": username, "password": "secret"}).status_code == 201
    response = client.post("/auth/login", json={"username": username, "password": "secret"})
    return {"Authorization": f"Bearer {response.json['token']}"}


def test_tasks_require_a_valid_token(client):
    assert client.get("/tasks").status_code == 401
    assert client.get("/tasks", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_register_login_and_password_is_hashed(client):
    assert client.post("/auth/register", json={"username": "alice", "password": "secret"}).status_code == 201
    login = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    assert login.status_code == 200
    assert login.json["token"].count(".") == 2
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        password_hash = connection.execute("SELECT password_hash FROM users").fetchone()[0]
    assert password_hash != "secret"


def test_users_only_see_and_update_their_own_tasks(client):
    alice = register_and_login(client, "alice")
    bob = register_and_login(client, "bob")
    task = client.post("/tasks", json={"title": "Alice task"}, headers=alice).json

    assert client.get("/tasks", headers=bob).json["data"] == []
    assert client.get(f"/tasks/{task['id']}", headers=bob).status_code == 404
    assert client.put(f"/tasks/{task['id']}", json={"title": "stolen"}, headers=bob).status_code == 404
    assert client.get(f"/tasks/{task['id']}", headers=alice).json["title"] == "Alice task"


def test_duplicate_user_is_rejected(client):
    assert client.post("/auth/register", json={"username": "alice", "password": "secret"}).status_code == 201
    assert client.post("/auth/register", json={"username": "alice", "password": "other"}).status_code == 409


def test_old_tasks_table_is_migrated_without_losing_rows(client, tmp_path):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, "
            "status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO tasks (title, created_at) VALUES ('legacy', '2020-01-01')")
    app.config["DATABASE"] = str(database)
    headers = register_and_login(client, "alice")
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(tasks)")}
        count = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    assert "owner_id" in columns
    assert count == 1
    assert client.get("/tasks", headers=headers).json["data"] == []


def test_completing_task_queues_owner_notification(client, monkeypatch):
    headers = register_and_login(client, "alice@example.com")
    task = client.post("/tasks", json={"title": "Ship feature"}, headers=headers).json
    queued = []
    monkeypatch.setattr(send_notification_email, "delay", lambda *args: queued.append(args))

    response = client.put(
        f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers
    )

    assert response.status_code == 200
    assert queued == [("alice@example.com", "Ship feature")]


def test_notification_is_not_queued_when_status_does_not_transition_to_completed(client, monkeypatch):
    headers = register_and_login(client, "alice@example.com")
    task = client.post("/tasks", json={"title": "Draft"}, headers=headers).json
    queued = []
    monkeypatch.setattr(send_notification_email, "delay", lambda *args: queued.append(args))

    client.put(f"/tasks/{task['id']}", json={"title": "Draft v2"}, headers=headers)
    client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)
    client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)

    assert queued == [("alice@example.com", "Draft v2")]


def test_tasks_are_cursor_paginated(client):
    headers = register_and_login(client, "alice")
    for title in ("one", "two", "three", "four", "five"):
        assert client.post("/tasks", json={"title": title}, headers=headers).status_code == 201

    first = client.get("/tasks?limit=2", headers=headers)
    assert first.status_code == 200
    assert [task["title"] for task in first.json["data"]] == ["five", "four"]
    assert first.json["total"] == 5
    assert first.json["next_cursor"] == str(first.json["data"][-1]["id"])

    second = client.get(f"/tasks?limit=2&cursor={first.json['next_cursor']}", headers=headers)
    assert [task["title"] for task in second.json["data"]] == ["three", "two"]
    assert second.json["next_cursor"] == str(second.json["data"][-1]["id"])

    third = client.get(f"/tasks?limit=2&cursor={second.json['next_cursor']}", headers=headers)
    assert [task["title"] for task in third.json["data"]] == ["one"]
    assert third.json["next_cursor"] is None
    assert client.get("/tasks?limit=101", headers=headers).status_code == 400


def test_rate_limit_returns_retry_after_for_authenticated_user(client):
    headers = register_and_login(client, "rate-limit-user")
    responses = [client.get("/tasks", headers=headers) for _ in range(101)]

    assert all(response.status_code == 200 for response in responses[:100])
    assert responses[100].status_code == 429
    assert responses[100].headers.get("Retry-After")
