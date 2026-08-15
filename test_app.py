import sqlite3

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr("app.DATABASE", str(database))
    from app import app, init_db, limiter

    init_db()
    app.config.update(TESTING=True)
    limiter.reset()
    with app.test_client() as test_client:
        yield test_client


def register(client, username):
    response = client.post("/auth/register", json={"username": username, "password": "secret"})
    assert response.status_code == 201


def login(client, username):
    response = client.post("/auth/login", json={"username": username, "password": "secret"})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json["token"]}


def test_register_and_login(client):
    register(client, "alice")
    response = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    assert response.status_code == 200
    assert response.json["token"]


def test_duplicate_and_invalid_login(client):
    register(client, "alice")
    assert client.post("/auth/register", json={"username": "alice", "password": "other"}).status_code == 409
    assert client.post("/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401


def test_tasks_require_authentication(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "secret"}).status_code == 401


def test_users_only_see_and_change_their_tasks(client):
    register(client, "alice")
    alice = login(client, "alice")
    task = client.post("/tasks", json={"title": "Alice task"}, headers=alice).json

    register(client, "bob")
    bob = login(client, "bob")
    assert client.get("/tasks", headers=bob).json["data"] == []
    assert client.get(f"/tasks/{task['id']}", headers=bob).status_code == 404
    assert client.put(f"/tasks/{task['id']}", json={"title": "changed"}, headers=bob).status_code == 404
    assert client.get("/tasks", headers=alice).json["data"][0]["title"] == "Alice task"


def test_existing_task_schema_is_migrated(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
    monkeypatch.setattr("app.DATABASE", str(database))
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)")
        conn.execute("INSERT INTO tasks VALUES (0, 'legacy', 'pending', '2020-01-01')")
    from app import init_db

    init_db()
    with sqlite3.connect(database) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        assert "owner_id" in columns
        assert conn.execute("SELECT title FROM tasks WHERE id = 0").fetchone()[0] == "legacy"


def test_completion_enqueues_notification(client, monkeypatch):
    register(client, "alice@example.com")
    alice = login(client, "alice@example.com")
    task = client.post("/tasks", json={"title": "Ship feature"}, headers=alice).json
    queued = []
    monkeypatch.setattr("app.send_notification_email.delay", lambda *args: queued.append(args))

    response = client.put(
        f"/tasks/{task['id']}", json={"status": "completed"}, headers=alice
    )

    assert response.status_code == 200
    assert queued == [("alice@example.com", "Ship feature")]


def test_notification_only_enqueues_on_status_transition(client, monkeypatch):
    register(client, "alice")
    alice = login(client, "alice")
    task = client.post("/tasks", json={"title": "Write docs"}, headers=alice).json
    queued = []
    monkeypatch.setattr("app.send_notification_email.delay", lambda *args: queued.append(args))

    client.put(f"/tasks/{task['id']}", json={"title": "Updated docs"}, headers=alice)
    client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=alice)
    client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=alice)

    assert queued == [("alice", "Updated docs")]


def test_tasks_are_cursor_paginated(client):
    register(client, "alice")
    alice = login(client, "alice")
    for title in ("first", "second", "third"):
        client.post("/tasks", json={"title": title}, headers=alice)

    first_page = client.get("/tasks?limit=2", headers=alice)
    assert first_page.status_code == 200
    assert [task["title"] for task in first_page.json["data"]] == ["third", "second"]
    assert first_page.json["total"] == 3
    assert first_page.json["next_cursor"] == str(first_page.json["data"][-1]["id"])

    cursor = first_page.json["next_cursor"]
    second_page = client.get(f"/tasks?cursor={cursor}&limit=2", headers=alice)
    assert [task["title"] for task in second_page.json["data"]] == ["first"]
    assert second_page.json["next_cursor"] is None
    assert second_page.json["total"] == 3


def test_pagination_limit_is_bounded(client):
    register(client, "alice")
    alice = login(client, "alice")
    assert client.get("/tasks?limit=0", headers=alice).status_code == 400
    assert client.get("/tasks?limit=101", headers=alice).status_code == 400
    assert client.get("/tasks?limit=abc", headers=alice).status_code == 400


def test_rate_limit_returns_retry_after(client):
    register(client, "alice")
    alice = login(client, "alice")
    for _ in range(100):
        assert client.get("/tasks", headers=alice).status_code == 200
    limited = client.get("/tasks", headers=alice)
    assert limited.status_code == 429
    assert limited.headers.get("Retry-After")


def test_rate_limit_applies_to_auth_endpoints(client):
    for index in range(100):
        response = client.post(
            "/auth/login", json={"username": f"missing-{index}", "password": "secret"}
        )
        assert response.status_code == 401
    assert client.post("/auth/login", json={"username": "missing", "password": "secret"}).status_code == 429
