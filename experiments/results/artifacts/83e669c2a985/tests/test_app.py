import sqlite3
from unittest.mock import Mock

import pytest
from limits.storage import MemoryStorage

import app as api


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DATABASE", str(tmp_path / "tasks.db"))
    api.init_db()
    api.app.config["TESTING"] = True
    api.limiter._storage = MemoryStorage()
    return api.app.test_client()


def register(client, username):
    response = client.post(
        "/auth/register", json={"username": username, "password": "password"}
    )
    assert response.status_code == 201


def token(client, username):
    response = client.post(
        "/auth/login", json={"username": username, "password": "password"}
    )
    assert response.status_code == 200
    return response.get_json()["token"]


def test_register_login_and_password_is_hashed(client):
    register(client, "alice")
    login = client.post(
        "/auth/login", json={"username": "alice", "password": "password"}
    )
    assert login.status_code == 200
    with api.get_db() as connection:
        row = connection.execute(
            "SELECT password_hash FROM users WHERE username = 'alice'"
        ).fetchone()
    assert row["password_hash"] != "password"


def test_tasks_require_valid_tokens(client):
    assert client.get("/tasks").status_code == 401
    assert client.get("/tasks", headers={"Authorization": "Bearer invalid"}).status_code == 401
    register(client, "alice")
    auth = {"Authorization": f"Bearer {token(client, 'alice')}"}
    assert client.get("/tasks", headers=auth).status_code == 200


def test_users_only_see_and_modify_their_own_tasks(client):
    register(client, "alice")
    register(client, "bob")
    alice_auth = {"Authorization": f"Bearer {token(client, 'alice')}"}
    bob_auth = {"Authorization": f"Bearer {token(client, 'bob')}"}
    created = client.post("/tasks", json={"title": "Alice task"}, headers=alice_auth)
    task_id = created.get_json()["id"]

    assert client.get("/tasks", headers=bob_auth).get_json() == {
        "data": [],
        "next_cursor": None,
        "total": 0,
    }
    assert client.get(f"/tasks/{task_id}", headers=bob_auth).status_code == 404
    assert client.put(
        f"/tasks/{task_id}", json={"status": "done"}, headers=bob_auth
    ).status_code == 404
    assert client.get("/tasks", headers=alice_auth).get_json()["data"][0]["title"] == "Alice task"


def test_completing_task_enqueues_owner_notification(client, monkeypatch):
    register(client, "alice@example.com")
    auth = {"Authorization": f"Bearer {token(client, 'alice@example.com')}"}
    created = client.post("/tasks", json={"title": "Write report"}, headers=auth)
    task_id = created.get_json()["id"]
    enqueue = Mock()
    monkeypatch.setattr(api.send_notification_email, "delay", enqueue)

    response = client.put(
        f"/tasks/{task_id}",
        json={"status": "completed"},
        headers=auth,
    )

    assert response.status_code == 200
    enqueue.assert_called_once_with("alice@example.com", "Write report")


def test_notification_only_runs_on_transition_to_completed(client, monkeypatch):
    register(client, "alice@example.com")
    auth = {"Authorization": f"Bearer {token(client, 'alice@example.com')}"}
    created = client.post("/tasks", json={"title": "Write report"}, headers=auth)
    task_id = created.get_json()["id"]
    enqueue = Mock()
    monkeypatch.setattr(api.send_notification_email, "delay", enqueue)

    client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=auth)
    client.put(f"/tasks/{task_id}", json={"title": "Final report"}, headers=auth)

    enqueue.assert_called_once_with("alice@example.com", "Write report")


def test_migration_adds_owner_id_and_preserves_existing_tasks(tmp_path, monkeypatch):
    database = tmp_path / "old.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES ('old', 'pending', '2024-01-01')"
        )
    monkeypatch.setattr(api, "DATABASE", str(database))
    api.init_db()
    with api.get_db() as connection:
        task = connection.execute("SELECT title, owner_id FROM tasks").fetchone()
    assert task["title"] == "old"
    assert task["owner_id"] is not None


def test_tasks_are_cursor_paginated(client):
    register(client, "alice")
    auth = {"Authorization": f"Bearer {token(client, 'alice')}"}
    for title in ("first", "second", "third"):
        assert client.post("/tasks", json={"title": title}, headers=auth).status_code == 201

    first_page = client.get("/tasks?limit=2", headers=auth)
    assert first_page.status_code == 200
    first_body = first_page.get_json()
    assert len(first_body["data"]) == 2
    assert first_body["total"] == 3
    assert first_body["next_cursor"] == str(first_body["data"][-1]["id"])

    second_page = client.get(
        f"/tasks?cursor={first_body['next_cursor']}&limit=2", headers=auth
    )
    second_body = second_page.get_json()
    assert second_page.status_code == 200
    assert [task["title"] for task in second_body["data"]] == ["first"]
    assert second_body["next_cursor"] is None
    assert second_body["total"] == 3


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "limit=bad", "cursor=bad"])
def test_invalid_pagination_parameters_are_rejected(client, query):
    register(client, "alice")
    auth = {"Authorization": f"Bearer {token(client, 'alice')}"}
    response = client.get(f"/tasks?{query}", headers=auth)
    assert response.status_code == 400


def test_rate_limit_returns_429_and_retry_after(client):
    register(client, "alice")
    auth = {"Authorization": f"Bearer {token(client, 'alice')}"}
    responses = [client.get("/tasks", headers=auth) for _ in range(101)]
    assert responses[-1].status_code == 429
    assert responses[-1].headers["Retry-After"]


def test_auth_endpoints_are_rate_limited(client):
    for index in range(101):
        response = client.post(
            "/auth/login", json={"username": f"missing-{index}", "password": "bad"}
        )
    assert response.status_code == 429
    assert response.headers["Retry-After"]
