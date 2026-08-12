import app as app_module
from celery_app import send_notification_email


def register(client, username="alice", password="secret", email=None):
    payload = {"username": username, "password": password}
    if email is not None:
        payload["email"] = email
    return client.post("/auth/register", json=payload)


def login(client, username="alice", password="secret"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_header(client, username="alice", password="secret"):
    token = login(client, username, password).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def create_task(client, headers, title="hello"):
    resp = client.post("/tasks", json={"title": title}, headers=headers)
    assert resp.status_code == 201
    return resp.get_json()


def record_delay(monkeypatch):
    calls = []

    def fake_delay(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(send_notification_email, "delay", fake_delay)
    return calls


# ── Trigger logic ─────────────────────────────────────────────

def test_completed_status_triggers_notification_email(client, monkeypatch):
    register(client, email="alice@example.com")
    headers = auth_header(client)
    task = create_task(client, headers)
    calls = record_delay(monkeypatch)

    resp = client.put(
        f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
    assert len(calls) == 1
    assert calls[0][0] == ("alice@example.com", "hello")


def test_notification_uses_username_when_no_email(client, monkeypatch):
    register(client)
    headers = auth_header(client)
    task = create_task(client, headers)
    calls = record_delay(monkeypatch)

    client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)
    assert len(calls) == 1
    assert calls[0][0] == ("alice", "hello")


def test_non_completed_status_does_not_trigger(client, monkeypatch):
    register(client)
    headers = auth_header(client)
    task = create_task(client, headers)
    calls = record_delay(monkeypatch)

    client.put(f"/tasks/{task['id']}", json={"status": "in_progress"}, headers=headers)
    client.put(f"/tasks/{task['id']}", json={"title": "renamed"}, headers=headers)
    assert calls == []


def test_already_completed_task_does_not_trigger_again(client, monkeypatch):
    register(client)
    headers = auth_header(client)
    task = create_task(client, headers)
    calls = record_delay(monkeypatch)

    client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)
    client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)
    assert len(calls) == 1


def test_completion_via_title_and_status_update_triggers(client, monkeypatch):
    register(client, email="owner@example.com")
    headers = auth_header(client)
    task = create_task(client, headers, title="old title")
    calls = record_delay(monkeypatch)

    resp = client.put(
        f"/tasks/{task['id']}",
        json={"title": "new title", "status": "completed"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert calls[0][0] == ("owner@example.com", "new title")


def test_response_is_not_blocked_by_email_dispatch(client, monkeypatch):
    register(client)
    headers = auth_header(client)
    task = create_task(client, headers)
    record_delay(monkeypatch)

    resp = client.put(
        f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers
    )
    assert resp.status_code == 200


# ── Eager end-to-end ──────────────────────────────────────────

def test_completed_task_sends_email_in_eager_mode(client, capsys):
    register(client, email="alice@example.com")
    headers = auth_header(client)
    task = create_task(client, headers)

    resp = client.put(
        f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers
    )
    assert resp.status_code == 200
    out = capsys.readouterr().out
    assert "alice@example.com" in out
    assert "hello" in out


# ── The task itself ───────────────────────────────────────────

def test_send_notification_email_task_prints_mock_email(capsys):
    result = send_notification_email("bob@example.com", "ship it")
    assert result == (
        "To: bob@example.com | Subject: Task completed | "
        "Body: Your task 'ship it' has been marked as completed."
    )
    out = capsys.readouterr().out
    assert "[mock email]" in out
    assert "bob@example.com" in out
    assert "ship it" in out


# ── Configuration ─────────────────────────────────────────────

def test_celery_config_has_broker_backend_and_routes():
    import celery_config

    assert celery_config.BROKER_URL.startswith("redis://")
    assert celery_config.RESULT_BACKEND.startswith("redis://")
    assert celery_config.TASK_ROUTES["notifications.send_notification_email"][
        "queue"
    ] == "emails"


def test_celery_app_uses_redis_broker_and_routes_task():
    from celery_app import celery_app

    assert celery_app.conf.broker_url.startswith("redis://")
    assert celery_app.conf.result_backend.startswith("redis://")
    assert celery_app.conf.task_routes["notifications.send_notification_email"][
        "queue"
    ] == "emails"
