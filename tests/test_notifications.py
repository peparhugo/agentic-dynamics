import os

import pytest

os.environ["DATABASE"] = "test_tasks.db"
os.environ["SECRET_KEY"] = "test-secret-key"
from unittest import mock

import app as task_app

task_app.init_db()


@pytest.fixture()
def client():
    task_app.app.config["TESTING"] = True
    with task_app.app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def clean_db():
    yield
    with task_app.get_db() as conn:
        conn.execute("DELETE FROM tasks")
        conn.execute("DELETE FROM users")
        conn.commit()


def register_and_login(client, username="alice", password="password123"):
    resp = client.post(
        "/auth/register", json={"username": username, "password": password}
    )
    assert resp.status_code == 201
    resp = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200
    return resp.get_json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def create_task(client, token, title="Buy milk"):
    resp = client.post("/tasks", json={"title": title}, headers=auth(token))
    assert resp.status_code == 201
    return resp.get_json()


@mock.patch("app.send_notification_email.delay")
def test_completing_task_triggers_notification(mock_delay, client):
    token = register_and_login(client)
    task = create_task(client, token, title="Finish report")
    resp = client.put(
        f"/tasks/{task['id']}",
        json={"status": "completed"},
        headers=auth(token),
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
    mock_delay.assert_called_once_with("alice", "Finish report")


@mock.patch("app.send_notification_email.delay")
def test_non_completed_status_does_not_trigger_notification(mock_delay, client):
    token = register_and_login(client)
    task = create_task(client, token, title="Do the dishes")
    resp = client.put(
        f"/tasks/{task['id']}",
        json={"status": "in_progress"},
        headers=auth(token),
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "in_progress"
    mock_delay.assert_not_called()


@mock.patch("app.send_notification_email.delay")
def test_already_completed_task_does_not_trigger_again(mock_delay, client):
    token = register_and_login(client)
    task = create_task(client, token, title="Ship it")
    client.put(
        f"/tasks/{task['id']}",
        json={"status": "completed"},
        headers=auth(token),
    )
    assert mock_delay.call_count == 1
    resp = client.put(
        f"/tasks/{task['id']}",
        json={"status": "completed"},
        headers=auth(token),
    )
    assert resp.status_code == 200
    mock_delay.assert_called_once_with("alice", "Ship it")


@mock.patch("app.send_notification_email.delay")
def test_notification_uses_user_email_when_registered(mock_delay, client):
    resp = client.post(
        "/auth/register",
        json={
            "username": "emily",
            "password": "password123",
            "email": "emily@example.com",
        },
    )
    assert resp.status_code == 201
    resp = client.post(
        "/auth/login", json={"username": "emily", "password": "password123"}
    )
    token = resp.get_json()["token"]
    task = create_task(client, token, title="Send email")
    client.put(
        f"/tasks/{task['id']}",
        json={"status": "completed"},
        headers=auth(token),
    )
    mock_delay.assert_called_once_with("emily@example.com", "Send email")


def test_send_notification_email_task_prints_mock(capsys):
    result = task_app.send_notification_email.run(
        "alice@example.com", "Finish report"
    )
    captured = capsys.readouterr()
    assert "alice@example.com" in captured.out
    assert "Finish report" in captured.out
    assert "Notification sent" in result


def test_send_notification_email_task_returns_result():
    result = task_app.send_notification_email.run(
        "bob@example.com", "Buy milk"
    )
    assert result == "Notification sent to bob@example.com for task 'Buy milk'"
