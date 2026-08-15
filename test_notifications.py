import pytest

import app as app_module


@pytest.fixture()
def notified(client, monkeypatch):
    calls = []

    def capture(*args, **kwargs):
        calls.append((args, kwargs))
        return None

    monkeypatch.setattr(app_module.send_notification_email, "delay", capture)
    return calls


def _email_of(call):
    return call[0][0]


def _title_of(call):
    return call[0][1]


# ── Notification trigger logic ────────────────────────────────

def test_completed_status_triggers_email(client, auth, notified):
    created = client.post("/tasks", json={"title": "alpha"}, headers=auth).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth
    )
    assert resp.status_code == 200
    assert len(notified) == 1
    assert _email_of(notified[0]) == "alice@example.com"
    assert _title_of(notified[0]) == "alpha"


def test_custom_email_used_in_notification(client, notified):
    resp = client.post(
        "/auth/register",
        json={"username": "maya", "password": "pw", "email": "maya@corp.io"},
    )
    assert resp.status_code == 201
    token = resp.get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post("/tasks", json={"title": "ship"}, headers=headers).get_json()
    client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
    )
    assert len(notified) == 1
    assert _email_of(notified[0]) == "maya@corp.io"


def test_non_completed_status_no_email(client, auth, notified):
    created = client.post("/tasks", json={"title": "alpha"}, headers=auth).get_json()
    client.put(
        f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=auth
    )
    assert notified == []


def test_title_only_update_no_email(client, auth, notified):
    created = client.post("/tasks", json={"title": "alpha"}, headers=auth).get_json()
    client.put(f"/tasks/{created['id']}", json={"title": "beta"}, headers=auth)
    assert notified == []


def test_already_completed_no_email(client, auth, notified):
    created = client.post("/tasks", json={"title": "alpha"}, headers=auth).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth
    )
    assert resp.status_code == 200
    assert len(notified) == 1
    client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth
    )
    assert len(notified) == 1


def test_email_only_sent_to_task_owner(client, auth, notified):
    bob = client.post(
        "/auth/register", json={"username": "bob", "password": "bobpass"}
    ).get_json()
    bob_auth = {"Authorization": f"Bearer {bob['token']}"}
    created = client.post(
        "/tasks", json={"title": "alice's task"}, headers=auth
    ).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=bob_auth
    )
    assert resp.status_code == 404
    assert notified == []

    client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth
    )
    assert len(notified) == 1
    assert _email_of(notified[0]) == "alice@example.com"
    assert _title_of(notified[0]) == "alice's task"


def test_email_not_sent_when_task_not_found(client, auth, notified):
    resp = client.put("/tasks/999", json={"status": "completed"}, headers=auth)
    assert resp.status_code == 404
    assert notified == []


def test_response_not_blocked_by_email(client, auth, notified):
    created = client.post("/tasks", json={"title": "alpha"}, headers=auth).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
