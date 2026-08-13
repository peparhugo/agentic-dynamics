import os
import sqlite3
import tempfile
from unittest.mock import patch

import pytest

from tasks_app import create_app


@pytest.fixture
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    app = create_app(database=path)
    app.testing = True
    with app.test_client() as client:
        yield client
    os.remove(path)


def register(client, username="alice", password="hunter2pass"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="hunter2pass"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_headers(client, username="alice", password="hunter2pass"):
    register(client, username, password)
    token = login(client, username, password).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def create_task(client, title="Buy milk", headers=None):
    if headers is None:
        headers = auth_headers(client)
    return client.post("/tasks", json={"title": title}, headers=headers)


# ── Auth: register ──────────────────────────────────────────────


def test_register_success(client):
    resp = register(client)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "alice"
    assert isinstance(data["id"], int)
    assert "password" not in data
    assert "password_hash" not in data


def test_register_missing_username_returns_400(client):
    resp = client.post("/auth/register", json={"password": "hunter2pass"})
    assert resp.status_code == 400


def test_register_missing_password_returns_400(client):
    resp = client.post("/auth/register", json={"username": "alice"})
    assert resp.status_code == 400


def test_register_duplicate_username_returns_409(client):
    register(client, "alice", "hunter2pass")
    resp = register(client, "alice", "otherpass123")
    assert resp.status_code == 409


# ── Auth: login ─────────────────────────────────────────────────


def test_login_success(client):
    register(client, "alice", "hunter2pass")
    resp = login(client, "alice", "hunter2pass")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data and isinstance(data["token"], str)


def test_login_wrong_password_returns_401(client):
    register(client, "alice", "hunter2pass")
    resp = login(client, "alice", "wrongpassword")
    assert resp.status_code == 401


def test_login_unknown_user_returns_401(client):
    resp = login(client, "ghost", "hunter2pass")
    assert resp.status_code == 401


# ── Auth: protection of /tasks ──────────────────────────────────


def test_tasks_requires_auth_missing_header_returns_401(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_tasks_requires_auth_invalid_token_returns_401(client):
    resp = client.get("/tasks", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_tasks_requires_auth_malformed_header_returns_401(client):
    resp = client.get("/tasks", headers={"Authorization": "not-bearer-token"})
    assert resp.status_code == 401


def test_create_task_without_auth_returns_401(client):
    resp = client.post("/tasks", json={"title": "Buy milk"})
    assert resp.status_code == 401


# ── Per-user task isolation ──────────────────────────────────────


def test_users_only_see_their_own_tasks(client):
    alice_headers = auth_headers(client, "alice", "hunter2pass")
    bob_headers = auth_headers(client, "bob", "swordfish123")

    create_task(client, "Alice task", headers=alice_headers)
    create_task(client, "Bob task", headers=bob_headers)

    alice_tasks = client.get("/tasks", headers=alice_headers).get_json()
    bob_tasks = client.get("/tasks", headers=bob_headers).get_json()

    assert [t["title"] for t in alice_tasks] == ["Alice task"]
    assert [t["title"] for t in bob_tasks] == ["Bob task"]


def test_get_other_users_task_returns_404(client):
    alice_headers = auth_headers(client, "alice", "hunter2pass")
    bob_headers = auth_headers(client, "bob", "swordfish123")

    created = create_task(client, "Alice task", headers=alice_headers).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=bob_headers)
    assert resp.status_code == 404


def test_update_other_users_task_returns_404(client):
    alice_headers = auth_headers(client, "alice", "hunter2pass")
    bob_headers = auth_headers(client, "bob", "swordfish123")

    created = create_task(client, "Alice task", headers=alice_headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "Hacked"}, headers=bob_headers
    )
    assert resp.status_code == 404


# ── Existing task behavior (now authenticated) ───────────────────


def test_create_task_success(client):
    headers = auth_headers(client)
    resp = create_task(client, "Write tests", headers=headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Write tests"
    assert data["status"] == "pending"
    assert isinstance(data["id"], int)
    assert "created_at" in data


def test_create_task_missing_title_returns_400(client):
    headers = auth_headers(client)
    resp = client.post("/tasks", json={}, headers=headers)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_create_task_blank_title_returns_400(client):
    headers = auth_headers(client)
    resp = client.post("/tasks", json={"title": "   "}, headers=headers)
    assert resp.status_code == 400


def test_create_task_no_body_returns_400(client):
    headers = auth_headers(client)
    resp = client.post("/tasks", headers=headers)
    assert resp.status_code == 400


def test_list_tasks_empty(client):
    headers = auth_headers(client)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_tasks_ordered_desc_by_created_at(client):
    headers = auth_headers(client)
    create_task(client, "First", headers=headers)
    create_task(client, "Second", headers=headers)
    create_task(client, "Third", headers=headers)

    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["Third", "Second", "First"]


def test_get_task_success(client):
    headers = auth_headers(client)
    created = create_task(client, "Read book", headers=headers).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == created["id"]
    assert data["title"] == "Read book"


def test_get_task_not_found(client):
    headers = auth_headers(client)
    resp = client.get("/tasks/999", headers=headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client):
    headers = auth_headers(client)
    created = create_task(client, "Old title", headers=headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "New title"}, headers=headers
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status(client):
    headers = auth_headers(client)
    created = create_task(client, "Task", headers=headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "done"}, headers=headers
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "done"
    assert data["title"] == "Task"


def test_update_task_title_and_status(client):
    headers = auth_headers(client)
    created = create_task(client, "Task", headers=headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "Updated", "status": "in_progress"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Updated"
    assert data["status"] == "in_progress"


def test_update_task_not_found(client):
    headers = auth_headers(client)
    resp = client.put("/tasks/999", json={"title": "x"}, headers=headers)
    assert resp.status_code == 404


def test_update_task_empty_body_returns_400(client):
    headers = auth_headers(client)
    created = create_task(client, "Task", headers=headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={}, headers=headers)
    assert resp.status_code == 400


def test_update_task_blank_title_returns_400(client):
    headers = auth_headers(client)
    created = create_task(client, "Task", headers=headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "   "}, headers=headers)
    assert resp.status_code == 400


# ── Completion notification trigger ───────────────────────────────


def test_update_task_to_completed_triggers_notification(client):
    headers = auth_headers(client)
    created = create_task(client, "Ship report", headers=headers).get_json()

    with patch("tasks_app.send_notification_email") as mock_task:
        resp = client.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
        )
        assert resp.status_code == 200
        mock_task.delay.assert_called_once_with("alice", "Ship report")


def test_update_task_to_non_completed_status_does_not_trigger_notification(client):
    headers = auth_headers(client)
    created = create_task(client, "Task", headers=headers).get_json()

    with patch("tasks_app.send_notification_email") as mock_task:
        resp = client.put(
            f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=headers
        )
        assert resp.status_code == 200
        mock_task.delay.assert_not_called()


def test_update_task_title_only_does_not_trigger_notification(client):
    headers = auth_headers(client)
    created = create_task(client, "Task", headers=headers).get_json()

    with patch("tasks_app.send_notification_email") as mock_task:
        resp = client.put(
            f"/tasks/{created['id']}", json={"title": "Renamed"}, headers=headers
        )
        assert resp.status_code == 200
        mock_task.delay.assert_not_called()


def test_update_task_already_completed_does_not_retrigger_notification(client):
    headers = auth_headers(client)
    created = create_task(client, "Task", headers=headers).get_json()

    with patch("tasks_app.send_notification_email") as mock_task:
        client.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
        )
        mock_task.delay.reset_mock()

        resp = client.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
        )
        assert resp.status_code == 200
        mock_task.delay.assert_not_called()


def test_update_task_completed_uses_owner_username_as_notification_recipient(client):
    alice_headers = auth_headers(client, "alice", "hunter2pass")
    created = create_task(client, "Alice task", headers=alice_headers).get_json()

    with patch("tasks_app.send_notification_email") as mock_task:
        client.put(
            f"/tasks/{created['id']}",
            json={"status": "completed"},
            headers=alice_headers,
        )
        mock_task.delay.assert_called_once_with("alice", "Alice task")


def test_notification_broker_failure_does_not_break_response(client):
    headers = auth_headers(client)
    created = create_task(client, "Task", headers=headers).get_json()

    with patch("tasks_app.send_notification_email") as mock_task:
        mock_task.delay.side_effect = ConnectionError("broker unavailable")
        resp = client.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "completed"


# ── Migration: pre-auth databases keep their data ────────────────


def test_migration_adds_owner_id_without_dropping_existing_rows():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        legacy = sqlite3.connect(path)
        legacy.execute(
            """
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
            """
        )
        legacy.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
            ("legacy task", "pending", "2020-01-01T00:00:00"),
        )
        legacy.commit()
        legacy.close()

        app = create_app(database=path)
        app.testing = True

        columns = {
            row[1]
            for row in sqlite3.connect(path).execute("PRAGMA table_info(tasks)")
        }
        assert "owner_id" in columns

        row = sqlite3.connect(path).execute(
            "SELECT title, owner_id FROM tasks WHERE title = 'legacy task'"
        ).fetchone()
        assert row == ("legacy task", None)
    finally:
        os.remove(path)
