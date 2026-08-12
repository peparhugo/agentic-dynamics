import sqlite3

import pytest
from werkzeug.security import check_password_hash


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.DATABASE", str(tmp_path / "tasks.db"))
    import app

    app.init_db()
    app.limiter.reset()
    return app.app.test_client()


def register(client, username):
    response = client.post("/auth/register", json={"username": username, "password": "secret"})
    assert response.status_code == 201
    return response.get_json()


def token(client, username):
    response = client.post("/auth/login", json={"username": username, "password": "secret"})
    assert response.status_code == 200
    return response.get_json()["token"]


def auth(token_value):
    return {"Authorization": f"Bearer {token_value}"}


def test_register_login_and_password_is_hashed(client):
    user = register(client, "alice")
    assert user["username"] == "alice"
    assert client.post("/auth/register", json={"username": "alice", "password": "other"}).status_code == 409
    assert client.post("/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401

    import app
    with app.get_db() as conn:
        stored = conn.execute("SELECT password_hash FROM users WHERE username = 'alice'").fetchone()[0]
    assert stored != "secret"
    assert check_password_hash(stored, "secret")
    assert token(client, "alice")


def test_tasks_require_authentication(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "x"}).status_code == 401
    assert client.get("/tasks/1").status_code == 401
    assert client.put("/tasks/1", json={"status": "done"}).status_code == 401
    assert client.get("/tasks", headers=auth("not-a-token")).status_code == 401


def test_users_only_see_and_modify_their_own_tasks(client):
    register(client, "alice")
    register(client, "bob")
    alice = token(client, "alice")
    bob = token(client, "bob")

    created = client.post("/tasks", headers=auth(alice), json={"title": "Alice task"})
    assert created.status_code == 201
    task_id = created.get_json()["id"]
    assert created.get_json()["owner_id"] == 1
    assert client.get("/tasks", headers=auth(bob)).get_json()["data"] == []
    assert client.get(f"/tasks/{task_id}", headers=auth(bob)).status_code == 404
    assert client.put(f"/tasks/{task_id}", headers=auth(bob), json={"status": "done"}).status_code == 404
    assert client.get("/tasks", headers=auth(alice)).get_json()["data"][0]["title"] == "Alice task"


def test_old_tasks_schema_is_migrated_without_data_loss(tmp_path, monkeypatch):
    database = tmp_path / "old.db"
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)")
        conn.execute("INSERT INTO tasks VALUES (1, 'legacy', 'pending', '2024-01-01T00:00:00')")

    monkeypatch.setattr("app.DATABASE", str(database))
    import app
    app.init_db()
    with app.get_db() as conn:
        row = conn.execute("SELECT title, owner_id FROM tasks WHERE id = 1").fetchone()
        columns = {item[1] for item in conn.execute("PRAGMA table_info(tasks)")}
    assert dict(row) == {"title": "legacy", "owner_id": None}
    assert "owner_id" in columns


def test_completing_task_enqueues_notification(client, monkeypatch):
    register(client, "alice@example.com")
    user_token = token(client, "alice@example.com")
    created = client.post(
        "/tasks", headers=auth(user_token), json={"title": "Write tests"}
    )
    calls = []
    monkeypatch.setattr(
        "app.send_notification_email.delay",
        lambda user_email, task_title: calls.append((user_email, task_title)),
    )

    response = client.put(
        f"/tasks/{created.get_json()['id']}",
        headers=auth(user_token),
        json={"status": "completed"},
    )

    assert response.status_code == 200
    assert calls == [("alice@example.com", "Write tests")]


def test_notification_only_sends_on_transition_to_completed(client, monkeypatch):
    register(client, "alice@example.com")
    user_token = token(client, "alice@example.com")
    created = client.post(
        "/tasks", headers=auth(user_token), json={"title": "Ship feature"}
    )
    calls = []
    monkeypatch.setattr(
        "app.send_notification_email.delay",
        lambda user_email, task_title: calls.append((user_email, task_title)),
    )

    task_url = f"/tasks/{created.get_json()['id']}"
    client.put(task_url, headers=auth(user_token), json={"status": "completed"})
    client.put(task_url, headers=auth(user_token), json={"title": "Shipped feature"})

    assert calls == [("alice@example.com", "Ship feature")]


def test_tasks_are_cursor_paginated(client):
    register(client, "pager")
    user_token = token(client, "pager")
    for title in ("one", "two", "three", "four", "five"):
        assert client.post("/tasks", headers=auth(user_token), json={"title": title}).status_code == 201

    first = client.get("/tasks?limit=2", headers=auth(user_token))
    first_body = first.get_json()
    assert first.status_code == 200
    assert [task["title"] for task in first_body["data"]] == ["five", "four"]
    assert first_body["total"] == 5
    assert first_body["next_cursor"] == first_body["data"][-1]["id"]

    second = client.get(
        f"/tasks?cursor={first_body['next_cursor']}&limit=2",
        headers=auth(user_token),
    )
    second_body = second.get_json()
    assert [task["title"] for task in second_body["data"]] == ["three", "two"]
    assert second_body["total"] == 5

    final = client.get(
        f"/tasks?cursor={second_body['next_cursor']}&limit=2",
        headers=auth(user_token),
    ).get_json()
    assert [task["title"] for task in final["data"]] == ["one"]
    assert final["next_cursor"] is None


def test_task_pagination_validates_limit(client):
    register(client, "limits")
    user_token = token(client, "limits")
    assert client.get("/tasks?limit=0", headers=auth(user_token)).status_code == 400
    assert client.get("/tasks?limit=101", headers=auth(user_token)).status_code == 400
    assert client.get("/tasks?cursor=not-an-id", headers=auth(user_token)).status_code == 400


def test_authenticated_user_rate_limit_returns_retry_after(client):
    register(client, "rate-limited")
    user_token = token(client, "rate-limited")
    headers = auth(user_token)

    responses = [client.get("/tasks", headers=headers) for _ in range(100)]
    assert all(response.status_code == 200 for response in responses)
    limited = client.get("/tasks", headers=headers)
    assert limited.status_code == 429
    assert limited.headers.get("Retry-After")
