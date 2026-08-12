"""
Tests for the async email notification system.

Covers:
 - celery_config.py exposes the expected broker/result backend/task routing
   settings, and the Celery app in tasks.py is configured from it.
 - send_notification_email (the Celery task) runs synchronously and returns
   the expected mocked "sent" result.
 - PUT /tasks/{id} triggers send_notification_email.delay(...) exactly once,
   with the task owner's email and the task's title, when (and only when)
   the status transitions *into* 'completed'.
 - The trigger is non-blocking: we assert on the queuing call (.delay)
   rather than waiting for real delivery, and the endpoint still returns
   its normal 200 response even when the underlying call is mocked out.
"""

import json

import pytest

import app as app_module
import celery_config
import tasks as tasks_module


# ── celery_config.py / tasks.py wiring ──────────────────────────────


def test_celery_config_has_broker_and_backend():
    assert celery_config.broker_url
    assert celery_config.result_backend


def test_celery_config_has_task_routes_for_notification_task():
    assert "tasks.send_notification_email" in celery_config.task_routes
    assert celery_config.task_routes["tasks.send_notification_email"]["queue"] == "notifications"


def test_celery_app_is_configured_from_celery_config():
    conf = tasks_module.celery_app.conf
    assert conf.broker_url == celery_config.broker_url
    assert conf.result_backend == celery_config.result_backend


def test_send_notification_email_task_runs_and_returns_sent_status(capsys):
    result = tasks_module.send_notification_email.run("alice@example.com", "Buy milk")
    assert result == {
        "to": "alice@example.com",
        "task_title": "Buy milk",
        "status": "sent",
    }
    captured = capsys.readouterr()
    assert "alice@example.com" in captured.out
    assert "Buy milk" in captured.out


# ── Trigger logic from PUT /tasks/{id} ──────────────────────────────


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test_notifications.db"
    monkeypatch.setattr(app_module, "DATABASE", str(db_path))
    app_module.init_db()

    # Avoid cross-test interference on the shared Redis-backed rate limiter.
    app_module.limiter.reset()

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client


@pytest.fixture()
def mock_delay(monkeypatch):
    """Replace send_notification_email.delay with a recorder so tests don't
    require a real Celery broker/worker, while still verifying the async
    (non-blocking) queuing call is made with the right arguments."""
    calls = []

    def fake_delay(user_email, task_title):
        calls.append((user_email, task_title))
        return "fake-task-id"

    monkeypatch.setattr(app_module.send_notification_email, "delay", fake_delay)
    return calls


def _register(client, username="alice", password="s3cret-pw", email=None):
    payload = {"username": username, "password": password}
    if email is not None:
        payload["email"] = email
    return client.post(
        "/auth/register",
        data=json.dumps(payload),
        content_type="application/json",
    )


def _login(client, username="alice", password="s3cret-pw"):
    return client.post(
        "/auth/login",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def _register_and_login(client, username="alice", password="s3cret-pw", email=None):
    _register(client, username, password, email)
    token = _login(client, username, password).get_json()["token"]
    return _auth_header(token)


def _create_task(client, headers, title="Buy milk"):
    return client.post(
        "/tasks",
        data=json.dumps({"title": title}),
        content_type="application/json",
        headers=headers,
    )


def test_register_stores_provided_email(client):
    resp = _register(client, "alice", "s3cret-pw", email="alice@work.com")
    assert resp.status_code == 201
    assert resp.get_json()["email"] == "alice@work.com"


def test_register_without_email_synthesizes_one(client):
    resp = _register(client, "alice", "s3cret-pw")
    assert resp.status_code == 201
    assert resp.get_json()["email"] == "alice@example.com"


def test_status_change_to_completed_triggers_notification(client, mock_delay):
    headers = _register_and_login(client, "alice", "pw", email="alice@work.com")
    created = _create_task(client, headers, "Write report").get_json()

    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "completed"}),
        content_type="application/json",
        headers=headers,
    )

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
    assert mock_delay == [("alice@work.com", "Write report")]


def test_notification_uses_synthesized_email_when_none_provided(client, mock_delay):
    headers = _register_and_login(client, "alice", "pw")
    created = _create_task(client, headers, "Write report").get_json()

    client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "completed"}),
        content_type="application/json",
        headers=headers,
    )

    assert mock_delay == [("alice@example.com", "Write report")]


def test_status_change_to_non_completed_does_not_trigger_notification(client, mock_delay):
    headers = _register_and_login(client)
    created = _create_task(client, headers, "Task").get_json()

    client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "in_progress"}),
        content_type="application/json",
        headers=headers,
    )

    assert mock_delay == []


def test_title_only_update_does_not_trigger_notification(client, mock_delay):
    headers = _register_and_login(client)
    created = _create_task(client, headers, "Task").get_json()

    client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"title": "Renamed"}),
        content_type="application/json",
        headers=headers,
    )

    assert mock_delay == []


def test_already_completed_task_updated_again_does_not_retrigger(client, mock_delay):
    headers = _register_and_login(client)
    created = _create_task(client, headers, "Task").get_json()

    client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "completed"}),
        content_type="application/json",
        headers=headers,
    )
    assert len(mock_delay) == 1

    # Updating an already-completed task (e.g. just changing the title)
    # while re-sending status='completed' should not send a second email.
    client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"title": "Still done", "status": "completed"}),
        content_type="application/json",
        headers=headers,
    )
    assert len(mock_delay) == 1


def test_update_on_missing_task_does_not_trigger_notification(client, mock_delay):
    headers = _register_and_login(client)
    resp = client.put(
        "/tasks/9999",
        data=json.dumps({"status": "completed"}),
        content_type="application/json",
        headers=headers,
    )
    assert resp.status_code == 404
    assert mock_delay == []


def test_notification_trigger_does_not_block_response(client, monkeypatch):
    """Verify the view queues the email via .delay() (non-blocking) rather
    than invoking the task's body (.run()) synchronously. We patch .run to
    raise if called directly, and .delay to a fast recorder, then confirm
    the endpoint still returns normally without ever hitting .run()."""
    calls = []

    def fake_delay(user_email, task_title):
        calls.append((user_email, task_title))
        return "queued"

    def blocking_run(*args, **kwargs):
        raise AssertionError(
            "the view must not call send_notification_email synchronously (use .delay)"
        )

    monkeypatch.setattr(app_module.send_notification_email, "delay", fake_delay)
    monkeypatch.setattr(app_module.send_notification_email, "run", blocking_run)

    headers = _register_and_login(client, "alice", "pw", email="alice@work.com")
    created = _create_task(client, headers, "Ship it").get_json()

    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "completed"}),
        content_type="application/json",
        headers=headers,
    )

    assert resp.status_code == 200
    assert calls == [("alice@work.com", "Ship it")]
