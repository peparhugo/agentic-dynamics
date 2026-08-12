import pytest

import app as app_module
from celery_tasks import send_notification_email


class _Recorder:
    """Stands in for the Celery task and records ``.delay`` calls."""

    def __init__(self):
        self.calls = []

    def delay(self, *args, **kwargs):
        self.calls.append((args, kwargs))


@pytest.fixture()
def client(tmp_path):
    app_module.DATA_FILE = str(tmp_path / "tasks.json")
    app_module.init_store()
    app_module.limiter.reset()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


@pytest.fixture()
def authed_client(client):
    resp = client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    )
    assert resp.status_code == 201
    login = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    token = login.get_json()["token"]
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client


@pytest.fixture()
def recorder(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(app_module, "send_notification_email", rec)
    return rec


def test_completion_triggers_notification(authed_client, recorder):
    created = authed_client.post("/tasks", json={"title": "Ship feature"}).get_json()
    resp = authed_client.put(f"/tasks/{created['id']}", json={"status": "completed"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
    assert len(recorder.calls) == 1
    args, _ = recorder.calls[0]
    assert args == ("alice@example.com", "Ship feature")


def test_completion_with_title_update_triggers_notification(authed_client, recorder):
    created = authed_client.post("/tasks", json={"title": "Old"}).get_json()
    resp = authed_client.put(
        f"/tasks/{created['id']}", json={"title": "New", "status": "completed"}
    )
    assert resp.status_code == 200
    assert len(recorder.calls) == 1
    args, _ = recorder.calls[0]
    assert args == ("alice@example.com", "New")


def test_no_notification_for_other_status(authed_client, recorder):
    created = authed_client.post("/tasks", json={"title": "WIP"}).get_json()
    resp = authed_client.put(f"/tasks/{created['id']}", json={"status": "in_progress"})
    assert resp.status_code == 200
    assert recorder.calls == []


def test_no_notification_when_already_completed(authed_client, recorder):
    created = authed_client.post("/tasks", json={"title": "Again"}).get_json()
    authed_client.put(f"/tasks/{created['id']}", json={"status": "completed"})
    authed_client.put(f"/tasks/{created['id']}", json={"status": "completed"})
    assert len(recorder.calls) == 1


def test_no_notification_for_title_only_update(authed_client, recorder):
    created = authed_client.post("/tasks", json={"title": "Rename me"}).get_json()
    resp = authed_client.put(f"/tasks/{created['id']}", json={"title": "Renamed"})
    assert resp.status_code == 200
    assert recorder.calls == []


def test_notification_uses_task_owner(authed_client, client, recorder):
    client.post("/auth/register", json={"username": "bob", "password": "pw"})
    bob_login = client.post("/auth/login", json={"username": "bob", "password": "pw"})
    bob_token = bob_login.get_json()["token"]

    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {bob_token}"
    created = client.post("/tasks", json={"title": "Bob's task"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "completed"})
    assert resp.status_code == 200
    assert len(recorder.calls) == 1
    args, _ = recorder.calls[0]
    assert args == ("bob@example.com", "Bob's task")


def test_email_task_exists_and_runs_async():
    assert send_notification_email is not None
    assert hasattr(send_notification_email, "delay")
    assert send_notification_email.name == "send_notification_email"


def test_email_task_returns_result_dict():
    result = send_notification_email("alice@example.com", "Ship feature")
    assert result["to"] == "alice@example.com"
    assert "Ship feature" in result["subject"]
