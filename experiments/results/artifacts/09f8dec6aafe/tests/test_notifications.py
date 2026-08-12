"""
Tests for the async "task completed" email notification trigger.

These tests never touch a real Celery broker/worker: they patch
``send_notification_email.delay`` (the call site used by the API) so the
trigger *logic* -- i.e. exactly when the API decides to enqueue a
notification -- can be verified quickly and deterministically.
"""

import json
from unittest.mock import patch

import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / "test_tasks.db"
    flask_app = create_app(database=str(db_path), jwt_secret="test-secret")
    flask_app.config.update(TESTING=True)
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, username="alice", password="s3cret-pw", email=None):
    payload = {"username": username, "password": password}
    if email is not None:
        payload["email"] = email
    return client.post(
        "/auth/register",
        data=json.dumps(payload),
        content_type="application/json",
    )


def login(client, username="alice", password="s3cret-pw"):
    return client.post(
        "/auth/login",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def token(client):
    register(client, "alice", "s3cret-pw")
    resp = login(client, "alice", "s3cret-pw")
    return resp.get_json()["token"]


def create(client, token, title="Buy milk"):
    return client.post(
        "/tasks",
        data=json.dumps({"title": title}),
        content_type="application/json",
        headers=auth_headers(token),
    )


def update(client, token, task_id, **fields):
    return client.put(
        f"/tasks/{task_id}",
        data=json.dumps(fields),
        content_type="application/json",
        headers=auth_headers(token),
    )


# ── Trigger fires on transition into 'completed' ────────────────

@patch("app.send_notification_email")
def test_completing_task_triggers_notification(mock_task, client, token):
    task = create(client, token, "Write report").get_json()

    resp = update(client, token, task["id"], status="completed")

    assert resp.status_code == 200
    mock_task.delay.assert_called_once_with("alice@example.com", "Write report")


@patch("app.send_notification_email")
def test_notification_uses_registered_email(mock_task, client):
    register(client, "bob", "pw", email="bob@work.example")
    token = login(client, "bob", "pw").get_json()["token"]
    task = create(client, token, "Ship release").get_json()

    update(client, token, task["id"], status="completed")

    mock_task.delay.assert_called_once_with("bob@work.example", "Ship release")


@patch("app.send_notification_email")
def test_notification_does_not_block_response(mock_task, client, token):
    """Even if the (mocked) task is slow, the HTTP response still returns."""
    mock_task.delay.side_effect = lambda *a, **k: None  # simulate fire-and-forget
    task = create(client, token, "Async check").get_json()

    resp = update(client, token, task["id"], status="completed")

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"


# ── Trigger does NOT fire for non-completing updates ────────────

@patch("app.send_notification_email")
def test_non_completed_status_does_not_trigger_notification(mock_task, client, token):
    task = create(client, token, "Task").get_json()

    update(client, token, task["id"], status="in_progress")

    mock_task.delay.assert_not_called()


@patch("app.send_notification_email")
def test_title_only_update_does_not_trigger_notification(mock_task, client, token):
    task = create(client, token, "Old title").get_json()

    update(client, token, task["id"], title="New title")

    mock_task.delay.assert_not_called()


@patch("app.send_notification_email")
def test_creating_task_does_not_trigger_notification(mock_task, client, token):
    create(client, token, "Fresh task")

    mock_task.delay.assert_not_called()


# ── No duplicate notifications on repeated saves ────────────────

@patch("app.send_notification_email")
def test_resaving_already_completed_task_does_not_retrigger(mock_task, client, token):
    task = create(client, token, "Task").get_json()
    update(client, token, task["id"], status="completed")
    assert mock_task.delay.call_count == 1

    # Saving 'completed' again (e.g. a no-op edit) must not resend the email.
    update(client, token, task["id"], status="completed")

    assert mock_task.delay.call_count == 1


@patch("app.send_notification_email")
def test_completing_then_reopening_then_completing_again_notifies_twice(
    mock_task, client, token
):
    task = create(client, token, "Task").get_json()

    update(client, token, task["id"], status="completed")
    update(client, token, task["id"], status="pending")
    update(client, token, task["id"], status="completed")

    assert mock_task.delay.call_count == 2


# ── Auth/ownership isolation still holds for the trigger path ──

@patch("app.send_notification_email")
def test_completing_another_users_task_returns_404_and_does_not_notify(
    mock_task, client
):
    register(client, "alice", "pw-alice")
    register(client, "bob", "pw-bob")
    token_alice = login(client, "alice", "pw-alice").get_json()["token"]
    token_bob = login(client, "bob", "pw-bob").get_json()["token"]

    alice_task = create(client, token_alice, "Secret task").get_json()

    resp = update(client, token_bob, alice_task["id"], status="completed")

    assert resp.status_code == 404
    mock_task.delay.assert_not_called()


# ── The Celery task itself ───────────────────────────────────────

def test_send_notification_email_task_runs_synchronously_and_returns_message():
    from tasks import send_notification_email

    result = send_notification_email("owner@example.com", "Do the thing")

    assert "owner@example.com" in result
    assert "Do the thing" in result


def test_celery_app_is_configured_with_redis_broker():
    from celery_app import celery_app

    assert celery_app.conf.broker_url.startswith("redis://")
    assert celery_app.conf.result_backend.startswith("redis://")
    assert "tasks.send_notification_email" in celery_app.conf.task_routes
