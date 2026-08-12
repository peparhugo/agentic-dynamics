import os
import time
from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE", str(tmp_path / "test.db"))
    import importlib
    import app as app_module

    app_module = importlib.reload(app_module)
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


@pytest.fixture()
def auth(client):
    def register(username="alice", password="secret123", email=None):
        payload = {"username": username, "password": password}
        if email is not None:
            payload["email"] = email
        return client.post("/auth/register", json=payload)

    def login(username="alice", password="secret123"):
        return client.post("/auth/login", json={"username": username, "password": password})

    def token(username="alice", password="secret123"):
        rv = login(username, password)
        assert rv.status_code == 200
        return rv.get_json()["token"]

    def headers(username="alice", password="secret123"):
        return {"Authorization": f"Bearer {token(username, password)}"}

    register()
    return {
        "register": register,
        "login": login,
        "token": token,
        "headers": headers,
    }


def post_task(client, title, username="alice", password="secret123"):
    return client.post(
        "/tasks",
        json={"title": title},
        headers={"Authorization": f"Bearer {auth_token(client, username, password)}"},
    )


def auth_token(client, username, password):
    rv = client.post("/auth/login", json={"username": username, "password": password})
    assert rv.status_code == 200
    return rv.get_json()["token"]


# ── Auth: register ────────────────────────────────────────────

def test_register_creates_user(client):
    rv = client.post("/auth/register", json={"username": "bob", "password": "hunter2"})
    assert rv.status_code == 201
    data = rv.get_json()
    assert data["id"] > 0
    assert data["username"] == "bob"
    assert "password_hash" not in data


def test_register_missing_fields_returns_400(client):
    rv = client.post("/auth/register", json={})
    assert rv.status_code == 400
    rv = client.post("/auth/register", json={"username": "bob"})
    assert rv.status_code == 400
    rv = client.post("/auth/register", json={"username": "   ", "password": "x"})
    assert rv.status_code == 400


def test_register_duplicate_username_returns_409(client, auth):
    rv = auth["register"]()
    assert rv.status_code == 409


# ── Auth: login ───────────────────────────────────────────────

def test_login_returns_token(client, auth):
    rv = auth["login"]()
    assert rv.status_code == 200
    token = rv.get_json()["token"]
    assert isinstance(token, str) and token


def test_login_wrong_password_returns_401(client, auth):
    rv = client.post("/auth/login", json={"username": "alice", "password": "wrong"})
    assert rv.status_code == 401


def test_login_unknown_user_returns_401(client):
    rv = client.post("/auth/login", json={"username": "nobody", "password": "x"})
    assert rv.status_code == 401


def test_passwords_are_hashed(client, auth):
    import app as app_module

    with app_module.get_db() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE username = 'alice'").fetchone()
    assert row is not None
    assert row["password_hash"] != "secret123"
    assert row["password_hash"].startswith("$2")


# ── Auth: protection ──────────────────────────────────────────

def test_tasks_require_token(client):
    rv = client.get("/tasks")
    assert rv.status_code == 401
    rv = client.post("/tasks", json={"title": "x"})
    assert rv.status_code == 401
    rv = client.get("/tasks/1")
    assert rv.status_code == 401
    rv = client.put("/tasks/1", json={"status": "done"})
    assert rv.status_code == 401


def test_tasks_reject_invalid_token(client):
    headers = {"Authorization": "Bearer not.a.token"}
    rv = client.get("/tasks", headers=headers)
    assert rv.status_code == 401


def test_tasks_reject_garbage_header(client):
    rv = client.get("/tasks", headers={"Authorization": "Basic abc123"})
    assert rv.status_code == 401


# ── Tasks (existing behavior, now authenticated) ─────────────

def test_create_task(client, auth):
    rv = post_task(client, "Write code")
    assert rv.status_code == 201
    data = rv.get_json()
    assert data["id"] > 0
    assert data["title"] == "Write code"
    assert data["status"] == "pending"
    assert isinstance(data["created_at"], int)


def test_create_task_missing_title_returns_400(client, auth):
    rv = client.post("/tasks", json={}, headers=auth["headers"]())
    assert rv.status_code == 400
    assert "error" in rv.get_json()

    rv = client.post("/tasks", json={"title": "   "}, headers=auth["headers"]())
    assert rv.status_code == 400


def test_list_tasks_ordered_by_created_at_desc(client, auth):
    post_task(client, "first")
    time.sleep(1.1)
    post_task(client, "second")
    time.sleep(1.1)
    post_task(client, "third")

    rv = client.get("/tasks", headers=auth["headers"]())
    assert rv.status_code == 200
    tasks = rv.get_json()
    assert [t["title"] for t in tasks] == ["third", "second", "first"]
    assert [t["created_at"] for t in tasks] == sorted(
        (t["created_at"] for t in tasks), reverse=True
    )


def test_get_task(client, auth):
    created = post_task(client, "Fetch me").get_json()
    rv = client.get(f"/tasks/{created['id']}", headers=auth["headers"]())
    assert rv.status_code == 200
    assert rv.get_json() == created


def test_get_task_not_found_returns_404(client, auth):
    rv = client.get("/tasks/9999", headers=auth["headers"]())
    assert rv.status_code == 404
    assert "error" in rv.get_json()


def test_update_task_title_and_status(client, auth):
    created = post_task(client, "Original").get_json()
    tid = created["id"]

    rv = client.put(
        f"/tasks/{tid}",
        json={"title": "Updated", "status": "done"},
        headers=auth["headers"](),
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["title"] == "Updated"
    assert data["status"] == "done"

    rv = client.put(f"/tasks/{tid}", json={"title": "Only title"}, headers=auth["headers"]())
    assert rv.get_json()["title"] == "Only title"
    assert rv.get_json()["status"] == "done"

    rv = client.put(f"/tasks/{tid}", json={"status": "in_progress"}, headers=auth["headers"]())
    assert rv.get_json()["status"] == "in_progress"
    assert rv.get_json()["title"] == "Only title"


def test_update_task_not_found_returns_404(client, auth):
    rv = client.put("/tasks/9999", json={"status": "done"}, headers=auth["headers"]())
    assert rv.status_code == 404
    assert "error" in rv.get_json()


# ── Per-user isolation ────────────────────────────────────────

def test_users_only_see_their_own_tasks(client, auth):
    auth["register"]("bob", "bobpass")
    bob_headers = auth["headers"]("bob", "bobpass")
    alice_headers = auth["headers"]()

    post_task(client, "alice task")
    rv = client.post("/tasks", json={"title": "bob task"}, headers=bob_headers)
    assert rv.status_code == 201

    alice_tasks = client.get("/tasks", headers=alice_headers).get_json()
    bob_tasks = client.get("/tasks", headers=bob_headers).get_json()
    assert [t["title"] for t in alice_tasks] == ["alice task"]
    assert [t["title"] for t in bob_tasks] == ["bob task"]


def test_user_cannot_read_another_users_task(client, auth):
    auth["register"]("bob", "bobpass")
    created = post_task(client, "secret").get_json()

    rv = client.get(f"/tasks/{created['id']}", headers=auth["headers"]("bob", "bobpass"))
    assert rv.status_code == 404


def test_user_cannot_update_another_users_task(client, auth):
    auth["register"]("bob", "bobpass")
    created = post_task(client, "secret").get_json()

    rv = client.put(
        f"/tasks/{created['id']}",
        json={"status": "done"},
        headers=auth["headers"]("bob", "bobpass"),
    )
    assert rv.status_code == 404


# ── Notification trigger (Celery) ─────────────────────────────

def test_completed_status_triggers_notification_email(client, auth, monkeypatch):
    import app as app_module

    mock_task = MagicMock()
    monkeypatch.setattr(app_module, "send_notification_email", mock_task)

    created = post_task(client, "Ship the release").get_json()

    rv = client.put(
        f"/tasks/{created['id']}",
        json={"status": "completed"},
        headers=auth["headers"](),
    )
    assert rv.status_code == 200
    assert rv.get_json()["status"] == "completed"

    mock_task.delay.assert_called_once()
    user_email, task_title = mock_task.delay.call_args[0]
    assert user_email == "alice"
    assert task_title == "Ship the release"


def test_completed_status_uses_registered_email(client, auth, monkeypatch):
    import app as app_module

    auth["register"]("bob", "bobpass", email="bob@example.com")
    bob_headers = auth["headers"]("bob", "bobpass")

    mock_task = MagicMock()
    monkeypatch.setattr(app_module, "send_notification_email", mock_task)

    created = client.post(
        "/tasks", json={"title": "Bob's task"}, headers=bob_headers
    ).get_json()

    rv = client.put(
        f"/tasks/{created['id']}",
        json={"status": "completed"},
        headers=bob_headers,
    )
    assert rv.status_code == 200

    mock_task.delay.assert_called_once()
    user_email, _ = mock_task.delay.call_args[0]
    assert user_email == "bob@example.com"


def test_non_completed_status_does_not_trigger_notification(client, auth, monkeypatch):
    import app as app_module

    mock_task = MagicMock()
    monkeypatch.setattr(app_module, "send_notification_email", mock_task)

    created = post_task(client, "Still in progress").get_json()

    rv = client.put(
        f"/tasks/{created['id']}",
        json={"status": "in_progress"},
        headers=auth["headers"](),
    )
    assert rv.status_code == 200
    mock_task.delay.assert_not_called()


def test_already_completed_task_does_not_retrigger_notification(client, auth, monkeypatch):
    import app as app_module

    mock_task = MagicMock()
    monkeypatch.setattr(app_module, "send_notification_email", mock_task)

    created = post_task(client, "Already done").get_json()
    headers = auth["headers"]()

    rv = client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers)
    assert rv.status_code == 200
    mock_task.delay.assert_called_once()

    rv = client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers)
    assert rv.status_code == 200
    mock_task.delay.assert_called_once()


def test_update_does_not_notify_for_unowned_task(client, auth, monkeypatch):
    import app as app_module

    auth["register"]("bob", "bobpass")
    mock_task = MagicMock()
    monkeypatch.setattr(app_module, "send_notification_email", mock_task)

    created = post_task(client, "alice secret").get_json()
    rv = client.put(
        f"/tasks/{created['id']}",
        json={"status": "completed"},
        headers=auth["headers"]("bob", "bobpass"),
    )
    assert rv.status_code == 404
    mock_task.delay.assert_not_called()


def test_send_notification_email_task_runs(capsys):
    from celery_config import send_notification_email

    result = send_notification_email("alice@example.com", "Finish report")
    assert "alice@example.com" in result
    assert "Finish report" in result
    captured = capsys.readouterr()
    assert "alice@example.com" in captured.out
