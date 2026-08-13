from unittest.mock import MagicMock

import app as app_module


def _mock_delay(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(app_module.send_notification_email, "delay", mock)
    return mock


def test_completing_task_triggers_notification(client, auth_headers, monkeypatch):
    mock_delay = _mock_delay(monkeypatch)

    created = client.post("/tasks", json={"title": "Ship feature"}, headers=auth_headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth_headers
    )

    assert resp.status_code == 200
    mock_delay.assert_called_once_with("alice@example.com", "Ship feature")


def test_non_completed_status_does_not_trigger_notification(client, auth_headers, monkeypatch):
    mock_delay = _mock_delay(monkeypatch)

    created = client.post("/tasks", json={"title": "Task"}, headers=auth_headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=auth_headers)

    assert resp.status_code == 200
    mock_delay.assert_not_called()


def test_title_only_update_does_not_trigger_notification(client, auth_headers, monkeypatch):
    mock_delay = _mock_delay(monkeypatch)

    created = client.post("/tasks", json={"title": "Task"}, headers=auth_headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "Renamed"}, headers=auth_headers)

    assert resp.status_code == 200
    mock_delay.assert_not_called()


def test_already_completed_task_does_not_retrigger_notification(client, auth_headers, monkeypatch):
    mock_delay = _mock_delay(monkeypatch)

    created = client.post("/tasks", json={"title": "Task"}, headers=auth_headers).get_json()
    client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth_headers)
    mock_delay.reset_mock()

    resp = client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth_headers)

    assert resp.status_code == 200
    mock_delay.assert_not_called()


def test_updating_missing_task_does_not_trigger_notification(client, auth_headers, monkeypatch):
    mock_delay = _mock_delay(monkeypatch)

    resp = client.put("/tasks/9999", json={"status": "completed"}, headers=auth_headers)

    assert resp.status_code == 404
    mock_delay.assert_not_called()


def test_notification_uses_correct_task_owner_email(client, monkeypatch):
    mock_delay = _mock_delay(monkeypatch)

    client.post("/auth/register", json={"username": "bob", "password": "secret123"})
    bob_login = client.post("/auth/login", json={"username": "bob", "password": "secret123"}).get_json()
    bob_headers = {"Authorization": f"Bearer {bob_login['token']}"}

    created = client.post("/tasks", json={"title": "Bob's task"}, headers=bob_headers).get_json()
    client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=bob_headers)

    mock_delay.assert_called_once_with("bob@example.com", "Bob's task")


def test_send_notification_email_task_logs_message(capsys):
    result = app_module.send_notification_email.run("alice@example.com", "Buy milk")

    assert "alice@example.com" in result
    assert "Buy milk" in result
    captured = capsys.readouterr()
    assert "alice@example.com" in captured.out
