import os
import tempfile

import pytest

import app as app_module


@pytest.fixture()
def client():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    os.unlink(path)
    app_module.DATABASE = path
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c
    if os.path.exists(path):
        os.unlink(path)


def register_and_login(client, username="alice", password="secret"):
    resp = client.post("/auth/register", json={"username": username, "password": password})
    assert resp.status_code == 201
    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ── Auth tests ────────────────────────────────────────────────

def test_register(client):
    resp = client.post("/auth/register", json={"username": "alice", "password": "secret"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["username"] == "alice"
    assert "password" not in data
    assert "password_hash" not in data


def test_register_duplicate_username(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    resp = client.post("/auth/register", json={"username": "alice", "password": "other"})
    assert resp.status_code == 409


def test_register_missing_fields(client):
    assert client.post("/auth/register", json={}).status_code == 400
    assert client.post("/auth/register", json={"username": "alice"}).status_code == 400
    assert client.post("/auth/register", json={"password": "secret"}).status_code == 400


def test_login_returns_token(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    resp = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    assert resp.status_code == 200
    assert "token" in resp.get_json()


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    resp = client.post("/auth/login", json={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post("/auth/login", json={"username": "nobody", "password": "secret"})
    assert resp.status_code == 401


# ── Protected endpoint auth tests ─────────────────────────────

def test_tasks_requires_token(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "x"}).status_code == 401
    assert client.get("/tasks/1").status_code == 401
    assert client.put("/tasks/1", json={"title": "x"}).status_code == 401


def test_tasks_invalid_token(client):
    headers = {"Authorization": "Bearer not-a-real-token"}
    assert client.get("/tasks", headers=headers).status_code == 401


def test_tasks_malformed_auth_header(client):
    headers = {"Authorization": "Basic abc123"}
    assert client.get("/tasks", headers=headers).status_code == 401


# ── Task tests (authenticated) ────────────────────────────────

def test_create_task(client):
    auth = register_and_login(client)
    resp = client.post("/tasks", json={"title": "Buy milk"}, headers=auth)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_create_task_missing_title(client):
    auth = register_and_login(client)
    resp = client.post("/tasks", json={}, headers=auth)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "title is required"


def test_create_task_empty_title(client):
    auth = register_and_login(client)
    resp = client.post("/tasks", json={"title": "   "}, headers=auth)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "title is required"


def test_list_tasks_ordered_desc(client):
    auth = register_and_login(client)
    client.post("/tasks", json={"title": "First"}, headers=auth)
    client.post("/tasks", json={"title": "Second"}, headers=auth)
    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 200
    data = resp.get_json()
    titles = [t["title"] for t in data]
    assert titles == ["Second", "First"]


def test_get_single_task(client):
    auth = register_and_login(client)
    created = client.post("/tasks", json={"title": "Read book"}, headers=auth).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=auth)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Read book"
    assert data["id"] == created["id"]


def test_get_task_not_found(client):
    auth = register_and_login(client)
    resp = client.get("/tasks/999", headers=auth)
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "task not found"


def test_update_task_title_and_status(client):
    auth = register_and_login(client)
    created = client.post("/tasks", json={"title": "Old"}, headers=auth).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "New", "status": "completed"},
        headers=auth,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New"
    assert data["status"] == "completed"


def test_update_task_partial(client):
    auth = register_and_login(client)
    created = client.post("/tasks", json={"title": "Only title"}, headers=auth).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"}, headers=auth)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Only title"
    assert data["status"] == "done"


def test_update_task_not_found(client):
    auth = register_and_login(client)
    resp = client.put("/tasks/999", json={"title": "Nope"}, headers=auth)
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "task not found"


# ── User isolation tests ──────────────────────────────────────

def test_users_only_see_their_own_tasks(client):
    alice = register_and_login(client, "alice", "secret")
    bob = register_and_login(client, "bob", "secret")

    alice_task = client.post("/tasks", json={"title": "Alice task"}, headers=alice).get_json()
    client.post("/tasks", json={"title": "Bob task"}, headers=bob)

    alice_tasks = client.get("/tasks", headers=alice).get_json()
    assert [t["title"] for t in alice_tasks] == ["Alice task"]

    bob_tasks = client.get("/tasks", headers=bob).get_json()
    assert [t["title"] for t in bob_tasks] == ["Bob task"]


def test_user_cannot_access_other_users_task(client):
    alice = register_and_login(client, "alice", "secret")
    bob = register_and_login(client, "bob", "secret")

    alice_task = client.post("/tasks", json={"title": "Private"}, headers=alice).get_json()

    resp = client.get(f"/tasks/{alice_task['id']}", headers=bob)
    assert resp.status_code == 404

    resp = client.put(f"/tasks/{alice_task['id']}", json={"title": "Hijack"}, headers=bob)
    assert resp.status_code == 404


# ── Notification trigger tests ────────────────────────────────

def test_completing_task_triggers_notification(client, mocker):
    auth = register_and_login(client)
    created = client.post("/tasks", json={"title": "Ship it"}, headers=auth).get_json()
    mock_delay = mocker.patch.object(app_module.send_notification_email, "delay")

    resp = client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth)

    assert resp.status_code == 200
    mock_delay.assert_called_once_with("alice@example.com", "Ship it")


def test_non_completed_status_does_not_trigger_notification(client, mocker):
    auth = register_and_login(client)
    created = client.post("/tasks", json={"title": "Ship it"}, headers=auth).get_json()
    mock_delay = mocker.patch.object(app_module.send_notification_email, "delay")

    resp = client.put(f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=auth)

    assert resp.status_code == 200
    mock_delay.assert_not_called()


def test_title_only_update_does_not_trigger_notification(client, mocker):
    auth = register_and_login(client)
    created = client.post("/tasks", json={"title": "Ship it"}, headers=auth).get_json()
    mock_delay = mocker.patch.object(app_module.send_notification_email, "delay")

    resp = client.put(f"/tasks/{created['id']}", json={"title": "Ship it v2"}, headers=auth)

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "pending"
    mock_delay.assert_not_called()


def test_repeated_completed_does_not_retrigger_notification(client, mocker):
    auth = register_and_login(client)
    created = client.post("/tasks", json={"title": "Ship it"}, headers=auth).get_json()
    mock_delay = mocker.patch.object(app_module.send_notification_email, "delay")

    client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth)
    client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth)

    mock_delay.assert_called_once()


def test_send_notification_email_task_mock():
    result = app_module.send_notification_email.run("alice@example.com", "Ship it")

    assert "alice@example.com" in result
    assert "Ship it" in result
