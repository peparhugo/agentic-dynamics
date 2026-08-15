import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path):
    app_module.DATABASE = str(tmp_path / "test.db")
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def register(client, username="alice", password="secret123"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="secret123"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_header(client, username="alice", password="secret123"):
    register(client, username, password)
    token = login(client, username, password).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ── Notification trigger logic ────────────────────────────────────

def test_status_change_to_completed_triggers_notification(client):
    headers = auth_header(client)
    created = client.post("/tasks", json={"title": "Ship feature"}, headers=headers).get_json()

    with patch("app.send_notification_email.delay") as mock_delay:
        resp = client.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
        )
        assert resp.status_code == 200
        mock_delay.assert_called_once_with("alice", "Ship feature")


def test_status_change_to_done_does_not_trigger_notification(client):
    headers = auth_header(client)
    created = client.post("/tasks", json={"title": "Ship feature"}, headers=headers).get_json()

    with patch("app.send_notification_email.delay") as mock_delay:
        resp = client.put(f"/tasks/{created['id']}", json={"status": "done"}, headers=headers)
        assert resp.status_code == 200
        mock_delay.assert_not_called()


def test_status_change_to_pending_does_not_trigger_notification(client):
    headers = auth_header(client)
    created = client.post("/tasks", json={"title": "Ship feature"}, headers=headers).get_json()

    with patch("app.send_notification_email.delay") as mock_delay:
        resp = client.put(f"/tasks/{created['id']}", json={"status": "pending"}, headers=headers)
        assert resp.status_code == 200
        mock_delay.assert_not_called()


def test_title_only_update_does_not_trigger_notification(client):
    headers = auth_header(client)
    created = client.post("/tasks", json={"title": "Ship feature"}, headers=headers).get_json()

    with patch("app.send_notification_email.delay") as mock_delay:
        resp = client.put(
            f"/tasks/{created['id']}", json={"title": "Ship feature v2"}, headers=headers
        )
        assert resp.status_code == 200
        mock_delay.assert_not_called()


def test_already_completed_task_does_not_retrigger_notification(client):
    headers = auth_header(client)
    created = client.post("/tasks", json={"title": "Ship feature"}, headers=headers).get_json()
    client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers)

    with patch("app.send_notification_email.delay") as mock_delay:
        resp = client.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
        )
        assert resp.status_code == 200
        mock_delay.assert_not_called()


def test_notification_uses_correct_task_owner(client):
    alice_headers = auth_header(client, "alice", "secret123")
    bob_headers = auth_header(client, "bob", "secret456")

    alice_task = client.post(
        "/tasks", json={"title": "Alice task"}, headers=alice_headers
    ).get_json()
    bob_task = client.post("/tasks", json={"title": "Bob task"}, headers=bob_headers).get_json()

    with patch("app.send_notification_email.delay") as mock_delay:
        client.put(
            f"/tasks/{alice_task['id']}", json={"status": "completed"}, headers=alice_headers
        )
        mock_delay.assert_called_once_with("alice", "Alice task")

    with patch("app.send_notification_email.delay") as mock_delay:
        client.put(f"/tasks/{bob_task['id']}", json={"status": "completed"}, headers=bob_headers)
        mock_delay.assert_called_once_with("bob", "Bob task")


def test_invalid_status_does_not_trigger_notification(client):
    headers = auth_header(client)
    created = client.post("/tasks", json={"title": "Ship feature"}, headers=headers).get_json()

    with patch("app.send_notification_email.delay") as mock_delay:
        resp = client.put(
            f"/tasks/{created['id']}", json={"status": "archived"}, headers=headers
        )
        assert resp.status_code == 422
        mock_delay.assert_not_called()


def test_completed_is_accepted_as_valid_status(client):
    headers = auth_header(client)
    created = client.post("/tasks", json={"title": "Ship feature"}, headers=headers).get_json()

    with patch("app.send_notification_email.delay"):
        resp = client.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
        )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "completed"


def test_send_notification_email_task_runs_synchronously():
    result = app_module.send_notification_email("alice", "Ship feature")
    assert "alice" in result
    assert "Ship feature" in result
