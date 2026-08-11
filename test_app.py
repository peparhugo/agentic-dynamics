import pytest
import os
import tempfile

import app as app_module
from app import app, init_db


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app_module.DATABASE = db_path
    init_db()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
    os.close(db_fd)
    os.unlink(db_path)


def auth_header(client, username="testuser", password="testpass"):
    resp = client.post("/auth/register", json={"username": username, "password": password})
    if resp.status_code == 409:
        pass
    resp = client.post("/auth/login", json={"username": username, "password": password})
    data = resp.get_json()
    return {"Authorization": f"Bearer {data['token']}"}


# ── Auth tests ──────────────────────────────────────────────────


def test_register(client):
    resp = client.post("/auth/register", json={"username": "alice", "password": "secret"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["message"] == "user created"
    assert data["user"]["id"] == 1
    assert data["user"]["username"] == "alice"
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]


def test_register_missing_username(client):
    resp = client.post("/auth/register", json={"password": "secret"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_missing_password(client):
    resp = client.post("/auth/register", json={"username": "bob"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_duplicate_username(client):
    client.post("/auth/register", json={"username": "dup", "password": "pass"})
    resp = client.post("/auth/register", json={"username": "dup", "password": "other"})
    assert resp.status_code == 409
    assert "error" in resp.get_json()


def test_login(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    resp = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    resp = client.post("/auth/login", json={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_nonexistent_user(client):
    resp = client.post("/auth/login", json={"username": "ghost", "password": "boo"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_missing_fields(client):
    resp = client.post("/auth/login", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_protected_route_no_token(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_protected_route_invalid_token(client):
    resp = client.get("/tasks", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_protected_route_malformed_header(client):
    resp = client.get("/tasks", headers={"Authorization": "NotBearer token"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_user_isolation(client):
    h1 = auth_header(client, "user1", "pass1")
    h2 = auth_header(client, "user2", "pass2")

    client.post("/tasks", json={"title": "User1 task"}, headers=h1)
    client.post("/tasks", json={"title": "User2 task"}, headers=h2)

    resp1 = client.get("/tasks", headers=h1)
    data1 = resp1.get_json()
    assert len(data1) == 1
    assert data1[0]["title"] == "User1 task"

    resp2 = client.get("/tasks", headers=h2)
    data2 = resp2.get_json()
    assert len(data2) == 1
    assert data2[0]["title"] == "User2 task"


def test_cannot_access_other_users_task(client):
    h1 = auth_header(client, "user1", "pass1")
    h2 = auth_header(client, "user2", "pass2")

    client.post("/tasks", json={"title": "User1 task"}, headers=h1)

    resp = client.get("/tasks/1", headers=h2)
    assert resp.status_code == 404

    resp = client.put("/tasks/1", json={"title": "Hacked"}, headers=h2)
    assert resp.status_code == 404


# ── Existing task route tests (with auth) ───────────────────────


def test_create_task(client):
    headers = auth_header(client)
    resp = client.post("/tasks", json={"title": "Buy groceries"}, headers=headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Buy groceries"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_create_task_missing_title(client):
    headers = auth_header(client)
    resp = client.post("/tasks", json={}, headers=headers)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_create_task_empty_title(client):
    headers = auth_header(client)
    resp = client.post("/tasks", json={"title": ""}, headers=headers)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_create_task_whitespace_title(client):
    headers = auth_header(client)
    resp = client.post("/tasks", json={"title": "   "}, headers=headers)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_list_tasks_empty(client):
    headers = auth_header(client)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == []


def test_list_tasks_order(client):
    headers = auth_header(client)
    client.post("/tasks", json={"title": "First"}, headers=headers)
    client.post("/tasks", json={"title": "Second"}, headers=headers)
    client.post("/tasks", json={"title": "Third"}, headers=headers)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 3
    assert data[0]["title"] == "Third"
    assert data[1]["title"] == "Second"
    assert data[2]["title"] == "First"


def test_get_task(client):
    headers = auth_header(client)
    client.post("/tasks", json={"title": "Test task"}, headers=headers)
    resp = client.get("/tasks/1", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Test task"
    assert data["status"] == "pending"


def test_get_task_not_found(client):
    headers = auth_header(client)
    resp = client.get("/tasks/999", headers=headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_update_task_title(client):
    headers = auth_header(client)
    client.post("/tasks", json={"title": "Old title"}, headers=headers)
    resp = client.put("/tasks/1", json={"title": "New title"}, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status(client):
    headers = auth_header(client)
    client.post("/tasks", json={"title": "Task"}, headers=headers)
    resp = client.put("/tasks/1", json={"status": "done"}, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Task"
    assert data["status"] == "done"


def test_update_task_both(client):
    headers = auth_header(client)
    client.post("/tasks", json={"title": "Old"}, headers=headers)
    resp = client.put("/tasks/1", json={"title": "Updated", "status": "in-progress"}, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Updated"
    assert data["status"] == "in-progress"


def test_update_task_not_found(client):
    headers = auth_header(client)
    resp = client.put("/tasks/999", json={"title": "Nope"}, headers=headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_update_task_no_fields(client):
    headers = auth_header(client)
    client.post("/tasks", json={"title": "Task"}, headers=headers)
    resp = client.put("/tasks/1", json={}, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Task"
    assert data["status"] == "pending"


# ── Model tests ─────────────────────────────────────────────────


def test_create_task_model():
    from app import create_task, get_task

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app_module.DATABASE = db_path
    init_db()
    try:
        task = create_task("Model test")
        assert task["id"] == 1
        assert task["title"] == "Model test"
        assert task["status"] == "pending"
        assert "created_at" in task

        fetched = get_task(1)
        assert fetched is not None
        assert fetched["id"] == 1
        assert fetched["title"] == "Model test"
        assert fetched["status"] == "pending"
    finally:
        os.close(db_fd)
        os.unlink(db_path)


def test_get_tasks_model():
    from app import create_task, get_tasks

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app_module.DATABASE = db_path
    init_db()
    try:
        create_task("A")
        create_task("B")
        tasks = get_tasks()
        assert len(tasks) == 2
        assert tasks[0]["title"] == "B"
        assert tasks[1]["title"] == "A"
    finally:
        os.close(db_fd)
        os.unlink(db_path)


def test_update_task_model():
    from app import create_task, update_task

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app_module.DATABASE = db_path
    init_db()
    try:
        create_task("Original")
        updated = update_task(1, title="Changed", status="completed")
        assert updated is not None
        assert updated["title"] == "Changed"
        assert updated["status"] == "completed"

        not_found = update_task(999, title="X")
        assert not_found is None
    finally:
        os.close(db_fd)
        os.unlink(db_path)


# ── Notification tests ───────────────────────────────────────────


def test_notification_sent_when_status_changes_to_completed(client, mocker):
    mock_delay = mocker.patch.object(app_module.send_notification_email, "delay")

    headers = auth_header(client, "notifyuser", "pass")
    client.post("/tasks", json={"title": "Notify me"}, headers=headers)

    resp = client.put("/tasks/1", json={"status": "completed"}, headers=headers)
    assert resp.status_code == 200

    mock_delay.assert_called_once_with(
        "notifyuser@example.com", "Notify me"
    )


def test_notification_not_sent_when_status_is_other(client, mocker):
    mock_delay = mocker.patch.object(app_module.send_notification_email, "delay")

    headers = auth_header(client, "user1", "pass")
    client.post("/tasks", json={"title": "Task"}, headers=headers)

    resp = client.put("/tasks/1", json={"status": "in-progress"}, headers=headers)
    assert resp.status_code == 200

    mock_delay.assert_not_called()


def test_notification_not_sent_when_already_completed(client, mocker):
    mock_delay = mocker.patch.object(app_module.send_notification_email, "delay")

    headers = auth_header(client, "user2", "pass")
    client.post("/tasks", json={"title": "Already done"}, headers=headers)
    client.put("/tasks/1", json={"status": "completed"}, headers=headers)

    mock_delay.reset_mock()

    resp = client.put("/tasks/1", json={"status": "completed"}, headers=headers)
    assert resp.status_code == 200

    mock_delay.assert_not_called()


def test_notification_not_sent_when_updating_title_only(client, mocker):
    mock_delay = mocker.patch.object(app_module.send_notification_email, "delay")

    headers = auth_header(client, "user3", "pass")
    client.post("/tasks", json={"title": "Title only"}, headers=headers)

    resp = client.put("/tasks/1", json={"title": "New title"}, headers=headers)
    assert resp.status_code == 200

    mock_delay.assert_not_called()


def test_notification_not_sent_when_no_status_change(client, mocker):
    mock_delay = mocker.patch.object(app_module.send_notification_email, "delay")

    headers = auth_header(client, "user4", "pass")
    client.post("/tasks", json={"title": "No change"}, headers=headers)

    resp = client.put("/tasks/1", json={}, headers=headers)
    assert resp.status_code == 200

    mock_delay.assert_not_called()
