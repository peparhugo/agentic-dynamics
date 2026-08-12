import importlib
from unittest import mock

import pytest

from celery_app import send_notification_email


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_notifications.db")
    monkeypatch.setenv("DATABASE", db_file)
    app = importlib.import_module("app")
    monkeypatch.setattr(app, "DATABASE", db_file)
    app.init_db()
    app.app.config["TESTING"] = True
    with app.app.test_client() as c:
        yield c


@pytest.fixture()
def auth(client):
    resp = client.post(
        "/auth/register",
        json={"username": "carol", "password": "secret", "email": "carol@acme.io"},
    )
    assert resp.status_code == 201
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def delay(monkeypatch):
    delay_mock = mock.MagicMock()
    app = importlib.import_module("app")
    monkeypatch.setattr(app.send_notification_email, "delay", delay_mock)
    return delay_mock


def _create(client, title, headers):
    return client.post("/tasks", json={"title": title}, headers=headers)


# --- trigger logic ---


def test_dispatch_notification_when_status_changes_to_completed(client, auth, delay):
    created = _create(client, "Write report", auth).get_json()

    resp = client.put(
        f"/tasks/{created['id']}",
        json={"status": "completed"},
        headers=auth,
    )

    assert resp.status_code == 200
    delay.assert_called_once_with("carol@acme.io", "Write report")


def test_no_dispatch_when_status_does_not_become_completed(client, auth, delay):
    created = _create(client, "Write report", auth).get_json()

    client.put(
        f"/tasks/{created['id']}",
        json={"status": "in_progress"},
        headers=auth,
    )

    delay.assert_not_called()


def test_no_dispatch_when_already_completed(client, auth, delay):
    created = _create(client, "Write report", auth).get_json()

    client.put(
        f"/tasks/{created['id']}",
        json={"status": "completed"},
        headers=auth,
    )
    client.put(
        f"/tasks/{created['id']}",
        json={"status": "completed"},
        headers=auth,
    )

    delay.assert_called_once_with("carol@acme.io", "Write report")


def test_dispatch_uses_task_title(client, auth, delay):
    created = _create(client, "First task", auth).get_json()

    client.put(
        f"/tasks/{created['id']}",
        json={"title": "Renamed task", "status": "completed"},
        headers=auth,
    )

    delay.assert_called_once_with("carol@acme.io", "Renamed task")


def test_default_email_used_when_not_provided(client, delay):
    resp = client.post(
        "/auth/register", json={"username": "dave", "password": "secret"}
    )
    assert resp.status_code == 201
    auth = {"Authorization": f"Bearer {resp.get_json()['token']}"}
    created = _create(client, "No email task", auth).get_json()

    client.put(
        f"/tasks/{created['id']}",
        json={"status": "completed"},
        headers=auth,
    )

    delay.assert_called_once_with("dave@example.com", "No email task")


# --- notification task itself ---


def test_send_notification_email_runs_and_logs(capsys):
    result = send_notification_email("carol@acme.io", "Write report")
    captured = capsys.readouterr()
    assert result == {
        "user_email": "carol@acme.io",
        "task_title": "Write report",
    }
    assert "carol@acme.io" in captured.out
    assert "Write report" in captured.out
