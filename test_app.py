import json
import os
import time
from unittest.mock import patch

import pytest

from app import app, init_db, migrate_db


@pytest.fixture
def client():
    app.config["TESTING"] = True
    import app as app_module

    app_module.DATABASE = "test_tasks.db"

    with app.test_client() as client:
        init_db()
        migrate_db()
        yield client

    if os.path.exists("test_tasks.db"):
        os.remove("test_tasks.db")


@pytest.fixture
def auth(client):
    client.post(
        "/auth/register",
        json={"username": "testuser", "password": "testpass"},
    )
    resp = client.post(
        "/auth/login",
        json={"username": "testuser", "password": "testpass"},
    )
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_two(client):
    client.post(
        "/auth/register",
        json={"username": "otheruser", "password": "otherpass"},
    )
    resp = client.post(
        "/auth/login",
        json={"username": "otheruser", "password": "otherpass"},
    )
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_task(client, auth):
    resp = client.post(
        "/tasks",
        json={"title": "Test task"},
        headers=auth,
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Test task"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_create_task_missing_title(client, auth):
    resp = client.post(
        "/tasks",
        json={},
        headers=auth,
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_no_body(client, auth):
    resp = client.post(
        "/tasks",
        content_type="application/json",
        headers=auth,
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks(client, auth):
    client.post(
        "/tasks",
        json={"title": "Task 1"},
        headers=auth,
    )
    time.sleep(0.01)
    client.post(
        "/tasks",
        json={"title": "Task 2"},
        headers=auth,
    )

    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2
    assert data[0]["title"] == "Task 2"
    assert data[1]["title"] == "Task 1"


def test_list_tasks_empty(client, auth):
    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_get_task(client, auth):
    client.post(
        "/tasks",
        json={"title": "Test task"},
        headers=auth,
    )
    resp = client.get("/tasks/1", headers=auth)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Test task"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_get_task_not_found(client, auth):
    resp = client.get("/tasks/999", headers=auth)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client, auth):
    client.post(
        "/tasks",
        json={"title": "Old title"},
        headers=auth,
    )
    resp = client.put(
        "/tasks/1",
        json={"title": "New title"},
        headers=auth,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status(client, auth):
    client.post(
        "/tasks",
        json={"title": "Task"},
        headers=auth,
    )
    resp = client.put(
        "/tasks/1",
        json={"status": "done"},
        headers=auth,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Task"
    assert data["status"] == "done"


def test_update_task_both(client, auth):
    client.post(
        "/tasks",
        json={"title": "Old"},
        headers=auth,
    )
    resp = client.put(
        "/tasks/1",
        json={"title": "New", "status": "done"},
        headers=auth,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New"
    assert data["status"] == "done"


def test_update_task_not_found(client, auth):
    resp = client.put(
        "/tasks/999",
        json={"title": "New"},
        headers=auth,
    )
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_created_at_is_iso_string(client, auth):
    resp = client.post(
        "/tasks",
        json={"title": "Time test"},
        headers=auth,
    )
    data = resp.get_json()
    assert isinstance(data["created_at"], str)
    assert "T" in data["created_at"]


def test_register(client):
    resp = client.post(
        "/auth/register",
        json={"username": "newuser", "password": "secret"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["username"] == "newuser"


def test_register_duplicate(client):
    client.post(
        "/auth/register",
        json={"username": "dup", "password": "secret"},
    )
    resp = client.post(
        "/auth/register",
        json={"username": "dup", "password": "secret2"},
    )
    assert resp.status_code == 409
    assert "error" in resp.get_json()


def test_register_missing_fields(client):
    resp = client.post(
        "/auth/register",
        json={"username": "user"},
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_no_body(client):
    resp = client.post(
        "/auth/register",
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_login(client):
    client.post(
        "/auth/register",
        json={"username": "loginuser", "password": "loginpass"},
    )
    resp = client.post(
        "/auth/login",
        json={"username": "loginuser", "password": "loginpass"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data
    assert isinstance(data["token"], str)


def test_login_wrong_password(client):
    client.post(
        "/auth/register",
        json={"username": "loginuser", "password": "correctpass"},
    )
    resp = client.post(
        "/auth/login",
        json={"username": "loginuser", "password": "wrongpass"},
    )
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_nonexistent_user(client):
    resp = client.post(
        "/auth/login",
        json={"username": "nobody", "password": "pass"},
    )
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_missing_fields(client):
    resp = client.post(
        "/auth/login",
        json={"username": "user"},
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_tasks_missing_token(client):
    resp = client.post("/tasks", json={"title": "Task"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_tasks_invalid_token(client):
    resp = client.get(
        "/tasks",
        headers={"Authorization": "Bearer invalid-token-here"},
    )
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_tasks_malformed_auth_header(client):
    resp = client.get(
        "/tasks",
        headers={"Authorization": "NotBearer token"},
    )
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_user_isolation(client, auth, auth_two):
    client.post(
        "/tasks",
        json={"title": "User 1 task"},
        headers=auth,
    )
    client.post(
        "/tasks",
        json={"title": "User 2 task"},
        headers=auth_two,
    )

    resp = client.get("/tasks", headers=auth)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["title"] == "User 1 task"


def test_cannot_get_other_user_task(client, auth, auth_two):
    client.post(
        "/tasks",
        json={"title": "User 1 task"},
        headers=auth,
    )
    client.post(
        "/tasks",
        json={"title": "User 2 task"},
        headers=auth_two,
    )

    resp = client.get("/tasks/2", headers=auth)
    assert resp.status_code == 404


def test_cannot_update_other_user_task(client, auth, auth_two):
    client.post(
        "/tasks",
        json={"title": "User 1 task"},
        headers=auth,
    )
    client.post(
        "/tasks",
        json={"title": "User 2 task"},
        headers=auth_two,
    )

    resp = client.put(
        "/tasks/2",
        json={"title": "Hacked"},
        headers=auth,
    )
    assert resp.status_code == 404


def test_update_task_to_completed_triggers_notification(client, auth):
    client.post(
        "/tasks",
        json={"title": "Complete me"},
        headers=auth,
    )

    with patch("app.send_notification_email.delay") as mock_delay:
        resp = client.put(
            "/tasks/1",
            json={"status": "completed"},
            headers=auth,
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "completed"
    mock_delay.assert_called_once_with("testuser@example.com", "Complete me")


def test_update_task_to_done_no_notification(client, auth):
    client.post(
        "/tasks",
        json={"title": "Just done"},
        headers=auth,
    )

    with patch("app.send_notification_email.delay") as mock_delay:
        resp = client.put(
            "/tasks/1",
            json={"status": "done"},
            headers=auth,
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "done"
    mock_delay.assert_not_called()


def test_update_task_title_no_notification(client, auth):
    client.post(
        "/tasks",
        json={"title": "Old title"},
        headers=auth,
    )

    with patch("app.send_notification_email.delay") as mock_delay:
        resp = client.put(
            "/tasks/1",
            json={"title": "New title"},
            headers=auth,
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    mock_delay.assert_not_called()
