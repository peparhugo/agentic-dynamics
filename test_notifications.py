import pytest

import app as app_module
import celery_config
import tasks


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DATABASE", str(tmp_path / "test.db"))
    app_module.init_db()
    app_module.migrate()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


@pytest.fixture()
def auth_headers(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    token = client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    ).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def sent(monkeypatch):
    calls = []
    monkeypatch.setattr(
        app_module.send_notification_email, "delay", lambda *args: calls.append(args)
    )
    return calls


def _create(client, title, headers):
    return client.post("/tasks", json={"title": title}, headers=headers)


def test_completing_task_triggers_notification(client, auth_headers, sent):
    created = _create(client, "Buy milk", auth_headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
    assert sent == [("alice@example.com", "Buy milk")]


def test_other_status_does_not_trigger_notification(client, auth_headers, sent):
    created = _create(client, "Buy milk", auth_headers).get_json()
    client.put(
        f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=auth_headers
    )
    client.put(
        f"/tasks/{created['id']}", json={"status": "pending"}, headers=auth_headers
    )
    assert sent == []


def test_title_update_does_not_trigger_notification(client, auth_headers, sent):
    created = _create(client, "Buy milk", auth_headers).get_json()
    client.put(
        f"/tasks/{created['id']}", json={"title": "Buy milk!"}, headers=auth_headers
    )
    assert sent == []


def test_completing_missing_task_does_not_trigger(client, auth_headers, sent):
    resp = client.put("/tasks/999", json={"status": "completed"}, headers=auth_headers)
    assert resp.status_code == 404
    assert sent == []


def test_re_completing_task_does_not_retrigger(client, auth_headers, sent):
    created = _create(client, "Buy milk", auth_headers).get_json()
    client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth_headers
    )
    client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth_headers
    )
    assert len(sent) == 1


def test_send_notification_email_task_logs(capsys):
    result = tasks.send_notification_email("alice@example.com", "Buy milk")
    assert result == "Notification email sent to alice@example.com: task 'Buy milk' has been completed."
    captured = capsys.readouterr()
    assert "alice@example.com" in captured.out
    assert "Buy milk" in captured.out


def test_celery_config_has_broker_backend_and_routes():
    assert celery_config.broker_url.startswith("redis://")
    assert celery_config.result_backend.startswith("redis://")
    assert celery_config.celery_app.conf.task_routes == {
        "tasks.send_notification_email": {"queue": "email"},
    }
