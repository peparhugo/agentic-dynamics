import pytest

import app as app_module
from celery_app import celery_app, send_notification_email


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE", str(db_path))
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    app_module.reset_rate_limits()
    celery_app.conf.task_always_eager = True
    with app_module.app.test_client() as c:
        yield c


def _register(client, username, password):
    return client.post("/auth/register", json={"username": username, "password": password})


def _login(client, username, password):
    return client.post("/auth/login", json={"username": username, "password": password})


def _token(client, username, password):
    return _login(client, username, password).get_json()["token"]


def _auth(client, username, password):
    return {"Authorization": f"Bearer {_token(client, username, password)}"}


@pytest.fixture()
def auth_headers(client):
    _register(client, "alice", "secret")
    return _auth(client, "alice", "secret")


def _create(client, title, headers):
    return client.post("/tasks", json={"title": title}, headers=headers)


# ── Notification trigger tests ────────────────────────────────


def test_completed_status_triggers_email(client, auth_headers, capsys):
    created = _create(client, "Ship the release", auth_headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
    out = capsys.readouterr().out
    assert "alice" in out
    assert "Ship the release" in out


def test_in_progress_status_does_not_trigger_email(client, auth_headers, capsys):
    created = _create(client, "Do not notify", auth_headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=auth_headers
    )
    assert resp.status_code == 200
    out = capsys.readouterr().out
    assert "notification" not in out
    assert "Do not notify" not in out


def test_title_only_update_does_not_trigger_email(client, auth_headers, capsys):
    created = _create(client, "Rename me", auth_headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "Renamed"}, headers=auth_headers
    )
    assert resp.status_code == 200
    out = capsys.readouterr().out
    assert "notification" not in out
    assert "Rename me" not in out


def test_send_notification_email_task_prints(capsys):
    send_notification_email("bob@example.com", "Finish the report")
    out = capsys.readouterr().out
    assert "bob@example.com" in out
    assert "Finish the report" in out
    assert "completed" in out


def test_notification_is_enqueued_not_blocking(client, auth_headers, monkeypatch):
    created = _create(client, "Async check", auth_headers).get_json()
    calls = []
    original = send_notification_email.delay

    def fake_delay(user_email, task_title):
        calls.append((user_email, task_title))

    monkeypatch.setattr(send_notification_email, "delay", fake_delay)
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert calls == [("alice", "Async check")]
