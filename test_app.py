import sqlite3
from unittest.mock import patch

import pytest
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter

import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(app, "DATABASE", str(database))
    app.init_db()
    app.app.config.update(TESTING=True)
    monkeypatch.setattr(app.limiter, "enabled", False)
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
    page = response.get_json()
    assert [task["id"] for task in page["data"]] == [second["id"], first["id"]]
    assert page["next_cursor"] is None
    assert page["total"] == 2


def test_list_tasks_uses_cursor_pagination(client):
    headers = auth_header(client)
    tasks = [client.post("/tasks", json={"title": f"Task {number}"}, headers=headers).get_json() for number in range(25)]

    first_page = client.get("/tasks?limit=20", headers=headers)

    assert first_page.status_code == 200
    first_data = first_page.get_json()
    assert [task["id"] for task in first_data["data"]] == [task["id"] for task in reversed(tasks[5:])]
    assert first_data["next_cursor"] == str(tasks[5]["id"])
    assert first_data["total"] == 25

    second_page = client.get(f"/tasks?cursor={first_data['next_cursor']}&limit=20", headers=headers)

    assert second_page.status_code == 200
    second_data = second_page.get_json()
    assert [task["id"] for task in second_data["data"]] == [task["id"] for task in reversed(tasks[:5])]
    assert second_data["next_cursor"] is None
    assert second_data["total"] == 25


@pytest.mark.parametrize("query", ["?limit=0", "?limit=101", "?limit=invalid", "?cursor=0", "?cursor=invalid"])
def test_list_tasks_rejects_invalid_pagination_parameters(client, query):
    response = client.get(f"/tasks{query}", headers=auth_header(client))

    assert response.status_code == 400


def test_rate_limit_returns_retry_after_header(client, monkeypatch):
    storage = MemoryStorage()
    monkeypatch.setattr(app.limiter, "_storage", storage)
    monkeypatch.setattr(app.limiter, "_limiter", FixedWindowRateLimiter(storage))
    monkeypatch.setattr(app.limiter, "enabled", True)
    headers = auth_header(client)

    for _ in range(100):
        assert client.get("/tasks", headers=headers).status_code == 200

    response = client.get("/tasks", headers=headers)

    assert response.status_code == 429
    assert response.headers["Retry-After"]


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


def test_completing_task_queues_notification_email(client):
    headers = auth_header(client, "alice", "secret")
    task = client.post("/tasks", json={"title": "Notify me"}, headers=headers).get_json()

    with patch("app.send_notification_email.delay") as delay:
        response = client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)

    assert response.status_code == 200
    delay.assert_called_once_with("alice", "Notify me")


def test_notification_only_queues_for_completion_transition(client):
    headers = auth_header(client, "alice", "secret")
    task = client.post("/tasks", json={"title": "Already done"}, headers=headers).get_json()

    with patch("app.send_notification_email.delay") as delay:
        client.put(f"/tasks/{task['id']}", json={"status": "done"}, headers=headers)
        client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)
        client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)

    delay.assert_called_once_with("alice", "Already done")


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
    assert client.get("/tasks", headers=bob).get_json()["data"] == []
    assert client.get(f"/tasks/{task['id']}", headers=bob).status_code == 404
    assert client.put(f"/tasks/{task['id']}", json={"status": "done"}, headers=bob).status_code == 404
