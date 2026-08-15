import json
from unittest.mock import patch

import pytest

from app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    storage_file = tmp_path / "tasks.json"
    monkeypatch.setenv("TASKS_FILE", str(storage_file))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-at-least-32-bytes-long")
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def register(client, username="alice", password="hunter2"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="hunter2"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def token(client):
    register(client)
    resp = login(client)
    return resp.get_json()["token"]


@pytest.fixture
def auth_client(client, token):
    """A thin wrapper exposing create() convenience with auth already applied."""
    return client, auth_headers(token)


def create(client, headers, title="Buy milk"):
    return client.post("/tasks", json={"title": title}, headers=headers)


# ---------------------------------------------------------------------------
# Auth: registration
# ---------------------------------------------------------------------------


def test_register_success(client):
    resp = register(client, "bob", "password123")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["username"] == "bob"
    assert "id" in body
    assert "password" not in body
    assert "password_hash" not in body


def test_register_missing_username(client):
    resp = client.post("/auth/register", json={"password": "x"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_missing_password(client):
    resp = client.post("/auth/register", json={"username": "bob"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_empty_username(client):
    resp = client.post("/auth/register", json={"username": "  ", "password": "x"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_duplicate_username(client):
    register(client, "bob", "password123")
    resp = register(client, "bob", "otherpassword")
    assert resp.status_code == 409
    assert "error" in resp.get_json()


def test_register_password_is_hashed_on_disk(client, tmp_path):
    register(client, "bob", "supersecret")
    storage_file = tmp_path / "tasks.json"
    contents = storage_file.read_text()
    assert "supersecret" not in contents
    assert "password_hash" in contents


# ---------------------------------------------------------------------------
# Auth: login
# ---------------------------------------------------------------------------


def test_login_success(client):
    register(client, "bob", "password123")
    resp = login(client, "bob", "password123")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "token" in body
    assert isinstance(body["token"], str)


def test_login_wrong_password(client):
    register(client, "bob", "password123")
    resp = login(client, "bob", "wrongpassword")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_unknown_user(client):
    resp = login(client, "ghost", "whatever")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_missing_fields(client):
    resp = client.post("/auth/login", json={"username": "bob"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


# ---------------------------------------------------------------------------
# Task endpoints require auth
# ---------------------------------------------------------------------------


def test_tasks_requires_auth_missing_header(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_tasks_requires_auth_malformed_header(client):
    resp = client.get("/tasks", headers={"Authorization": "not-a-bearer-token"})
    assert resp.status_code == 401


def test_tasks_requires_auth_invalid_token(client):
    resp = client.get("/tasks", headers={"Authorization": "Bearer garbage.token.value"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_create_task_requires_auth(client):
    resp = client.post("/tasks", json={"title": "x"})
    assert resp.status_code == 401


def test_get_task_requires_auth(client, auth_client):
    c, headers = auth_client
    created = create(c, headers, "task").get_json()
    resp = c.get(f"/tasks/{created['id']}")
    assert resp.status_code == 401


def test_update_task_requires_auth(client, auth_client):
    c, headers = auth_client
    created = create(c, headers, "task").get_json()
    resp = c.put(f"/tasks/{created['id']}", json={"title": "y"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Per-user task isolation
# ---------------------------------------------------------------------------


def test_users_only_see_own_tasks(client):
    register(client, "alice", "password1")
    register(client, "bob", "password2")
    alice_token = login(client, "alice", "password1").get_json()["token"]
    bob_token = login(client, "bob", "password2").get_json()["token"]
    alice_headers = auth_headers(alice_token)
    bob_headers = auth_headers(bob_token)

    create(client, alice_headers, "alice task")
    create(client, bob_headers, "bob task")

    alice_tasks = client.get("/tasks", headers=alice_headers).get_json()
    bob_tasks = client.get("/tasks", headers=bob_headers).get_json()

    assert [t["title"] for t in alice_tasks] == ["alice task"]
    assert [t["title"] for t in bob_tasks] == ["bob task"]


def test_cannot_get_other_users_task(client):
    register(client, "alice", "password1")
    register(client, "bob", "password2")
    alice_headers = auth_headers(login(client, "alice", "password1").get_json()["token"])
    bob_headers = auth_headers(login(client, "bob", "password2").get_json()["token"])

    alice_task = create(client, alice_headers, "alice task").get_json()

    resp = client.get(f"/tasks/{alice_task['id']}", headers=bob_headers)
    assert resp.status_code == 404


def test_cannot_update_other_users_task(client):
    register(client, "alice", "password1")
    register(client, "bob", "password2")
    alice_headers = auth_headers(login(client, "alice", "password1").get_json()["token"])
    bob_headers = auth_headers(login(client, "bob", "password2").get_json()["token"])

    alice_task = create(client, alice_headers, "alice task").get_json()

    resp = client.put(
        f"/tasks/{alice_task['id']}", json={"title": "hijacked"}, headers=bob_headers
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Task CRUD (authenticated)
# ---------------------------------------------------------------------------


def test_create_task_success(auth_client):
    c, headers = auth_client
    resp = create(c, headers, "Write report")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["id"] == 1
    assert body["title"] == "Write report"
    assert body["status"] == "pending"
    assert "created_at" in body


def test_create_task_missing_title(auth_client):
    c, headers = auth_client
    resp = c.post("/tasks", json={}, headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_empty_title(auth_client):
    c, headers = auth_client
    resp = c.post("/tasks", json={"title": "   "}, headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_non_string_title(auth_client):
    c, headers = auth_client
    resp = c.post("/tasks", json={"title": 123}, headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_no_body(auth_client):
    c, headers = auth_client
    resp = c.post("/tasks", headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_empty(auth_client):
    c, headers = auth_client
    resp = c.get("/tasks", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_tasks_ordered_desc(auth_client):
    c, headers = auth_client
    create(c, headers, "first")
    create(c, headers, "second")
    create(c, headers, "third")

    resp = c.get("/tasks", headers=headers)
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["third", "second", "first"]


def test_get_task_success(auth_client):
    c, headers = auth_client
    created = create(c, headers, "Read book").get_json()
    resp = c.get(f"/tasks/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json() == created


def test_get_task_not_found(auth_client):
    c, headers = auth_client
    resp = c.get("/tasks/999", headers=headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(auth_client):
    c, headers = auth_client
    created = create(c, headers, "old title").get_json()
    resp = c.put(f"/tasks/{created['id']}", json={"title": "new title"}, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "new title"
    assert body["status"] == "pending"


def test_update_task_status(auth_client):
    c, headers = auth_client
    created = create(c, headers, "task").get_json()
    resp = c.put(f"/tasks/{created['id']}", json={"status": "done"}, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "done"
    assert body["title"] == "task"


def test_update_task_title_and_status(auth_client):
    c, headers = auth_client
    created = create(c, headers, "task").get_json()
    resp = c.put(
        f"/tasks/{created['id']}",
        json={"title": "updated", "status": "in_progress"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "updated"
    assert body["status"] == "in_progress"


def test_update_task_not_found(auth_client):
    c, headers = auth_client
    resp = c.put("/tasks/999", json={"title": "x"}, headers=headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_no_fields(auth_client):
    c, headers = auth_client
    created = create(c, headers, "task").get_json()
    resp = c.put(f"/tasks/{created['id']}", json={}, headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_update_task_empty_title(auth_client):
    c, headers = auth_client
    created = create(c, headers, "task").get_json()
    resp = c.put(f"/tasks/{created['id']}", json={"title": "  "}, headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_data_persisted_to_flat_file(auth_client, tmp_path):
    c, headers = auth_client
    create(c, headers, "persisted task")
    storage_file = tmp_path / "tasks.json"
    assert storage_file.exists()
    contents = storage_file.read_text()
    assert "persisted task" in contents


# ---------------------------------------------------------------------------
# Completion notification trigger
# ---------------------------------------------------------------------------


def test_status_change_to_completed_triggers_notification(auth_client):
    c, headers = auth_client
    created = create(c, headers, "task").get_json()
    with patch("app.send_notification_email") as mock_task:
        resp = c.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
        )
    assert resp.status_code == 200
    mock_task.delay.assert_called_once()
    email_arg, title_arg = mock_task.delay.call_args[0]
    assert "alice" in email_arg
    assert title_arg == "task"


def test_status_change_to_non_completed_does_not_trigger_notification(auth_client):
    c, headers = auth_client
    created = create(c, headers, "task").get_json()
    with patch("app.send_notification_email") as mock_task:
        resp = c.put(
            f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=headers
        )
    assert resp.status_code == 200
    mock_task.delay.assert_not_called()


def test_title_only_update_does_not_trigger_notification(auth_client):
    c, headers = auth_client
    created = create(c, headers, "task").get_json()
    with patch("app.send_notification_email") as mock_task:
        resp = c.put(
            f"/tasks/{created['id']}", json={"title": "new title"}, headers=headers
        )
    assert resp.status_code == 200
    mock_task.delay.assert_not_called()


def test_already_completed_task_does_not_retrigger_notification(auth_client):
    c, headers = auth_client
    created = create(c, headers, "task").get_json()
    c.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers)

    with patch("app.send_notification_email") as mock_task:
        resp = c.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
        )
    assert resp.status_code == 200
    mock_task.delay.assert_not_called()


def test_notification_not_triggered_for_other_users_task(client):
    register(client, "alice", "password1")
    register(client, "bob", "password2")
    alice_headers = auth_headers(login(client, "alice", "password1").get_json()["token"])
    bob_headers = auth_headers(login(client, "bob", "password2").get_json()["token"])

    alice_task = create(client, alice_headers, "alice task").get_json()

    with patch("app.send_notification_email") as mock_task:
        resp = client.put(
            f"/tasks/{alice_task['id']}",
            json={"status": "completed"},
            headers=bob_headers,
        )
    assert resp.status_code == 404
    mock_task.delay.assert_not_called()


def test_notification_failure_does_not_break_response(auth_client):
    c, headers = auth_client
    created = create(c, headers, "task").get_json()
    with patch("app.send_notification_email") as mock_task:
        mock_task.delay.side_effect = Exception("broker unavailable")
        resp = c.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
        )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "completed"


# ---------------------------------------------------------------------------
# Migration: pre-existing data files without users/owner_id must not break
# ---------------------------------------------------------------------------


def test_migration_preserves_legacy_tasks_without_owner(tmp_path, monkeypatch):
    storage_file = tmp_path / "tasks.json"
    legacy_data = {
        "next_id": 3,
        "tasks": [
            {
                "id": 1,
                "title": "legacy task",
                "status": "pending",
                "created_at": "2024-01-01T00:00:00",
            },
            {
                "id": 2,
                "title": "legacy task 2",
                "status": "done",
                "created_at": "2024-01-02T00:00:00",
            },
        ],
    }
    storage_file.write_text(json.dumps(legacy_data))

    monkeypatch.setenv("TASKS_FILE", str(storage_file))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-at-least-32-bytes-long")
    flask_app = create_app()
    flask_app.config["TESTING"] = True

    migrated = json.loads(storage_file.read_text())
    assert migrated["users"] == []
    assert migrated["next_user_id"] == 1
    assert all(t["owner_id"] is None for t in migrated["tasks"])
    assert len(migrated["tasks"]) == 2

    with flask_app.test_client() as c:
        resp = register(c, "newuser", "password123")
        assert resp.status_code == 201
        token = login(c, "newuser", "password123").get_json()["token"]

        create_resp = c.post(
            "/tasks", json={"title": "new task"}, headers=auth_headers(token)
        )
        assert create_resp.status_code == 201

        list_resp = c.get("/tasks", headers=auth_headers(token))
        titles = [t["title"] for t in list_resp.get_json()]
        assert titles == ["new task"]

        legacy_resp = c.get("/tasks/1", headers=auth_headers(token))
        assert legacy_resp.status_code == 404
