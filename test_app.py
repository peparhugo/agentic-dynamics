import os
import tempfile
from unittest import mock

import pytest

import app as task_app


@pytest.fixture()
def client():
    task_app.app.config["TESTING"] = True
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    task_app.DATABASE = db_path
    task_app.init_db()
    with task_app.app.test_client() as c:
        yield c
    os.unlink(db_path)


def register_and_login(client, username="alice", password="secret-pass"):
    resp = client.post(
        "/auth/register", json={"username": username, "password": password}
    )
    assert resp.status_code == 201
    resp = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200
    return resp.get_json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── Auth ────────────────────────────────────────────────────────


def test_register(client):
    resp = client.post(
        "/auth/register", json={"username": "bob", "password": "hunter22"}
    )
    assert resp.status_code == 201
    assert resp.get_json()["username"] == "bob"


def test_register_requires_username_and_password(client):
    resp = client.post("/auth/register", json={})
    assert resp.status_code == 400


def test_register_duplicate_username(client):
    register_and_login(client, username="dup")
    resp = client.post(
        "/auth/register", json={"username": "dup", "password": "another-pass"}
    )
    assert resp.status_code == 409


def test_login_returns_token(client):
    register_and_login(client)
    resp = client.post(
        "/auth/login", json={"username": "alice", "password": "secret-pass"}
    )
    assert resp.status_code == 200
    assert resp.get_json()["token"]


def test_login_invalid_credentials(client):
    resp = client.post(
        "/auth/login", json={"username": "nobody", "password": "wrong"}
    )
    assert resp.status_code == 401


# ── Missing / invalid tokens ────────────────────────────────────


def test_tasks_require_auth(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "x"}).status_code == 401
    assert client.get("/tasks/1").status_code == 401
    assert client.put("/tasks/1", json={"title": "x"}).status_code == 401


def test_tasks_reject_invalid_token(client):
    headers = auth("not-a-real-token")
    assert client.get("/tasks", headers=headers).status_code == 401


# ── Tasks with auth ─────────────────────────────────────────────


def test_create_task(client):
    token = register_and_login(client)
    resp = client.post(
        "/tasks", json={"title": "Write code"}, headers=auth(token)
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Write code"
    assert data["status"] == "pending"
    assert isinstance(data["id"], int)
    assert data["created_at"]


def test_create_task_missing_title(client):
    token = register_and_login(client)
    resp = client.post("/tasks", json={}, headers=auth(token))
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_ordered_by_created_at_desc(client):
    token = register_and_login(client)
    for title in ["first", "second", "third"]:
        client.post("/tasks", json={"title": title}, headers=auth(token))
    resp = client.get("/tasks", headers=auth(token))
    assert resp.status_code == 200
    tasks = resp.get_json()
    assert [t["title"] for t in tasks] == ["third", "second", "first"]


def test_get_task(client):
    token = register_and_login(client)
    created = client.post(
        "/tasks", json={"title": "Find me"}, headers=auth(token)
    ).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=auth(token))
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Find me"


def test_get_task_not_found(client):
    token = register_and_login(client)
    resp = client.get("/tasks/9999", headers=auth(token))
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "task not found"}


def test_update_task(client):
    token = register_and_login(client)
    created = client.post(
        "/tasks", json={"title": "Old title"}, headers=auth(token)
    ).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "New title", "status": "done"},
        headers=auth(token),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "done"
    assert data["id"] == created["id"]


# ── Notification trigger ────────────────────────────────────────


def test_update_task_to_completed_triggers_notification(client):
    token = register_and_login(client)
    created = client.post(
        "/tasks", json={"title": "Ship feature"}, headers=auth(token)
    ).get_json()
    with mock.patch.object(task_app.send_notification_email, "delay") as delay:
        resp = client.put(
            f"/tasks/{created['id']}",
            json={"status": "completed"},
            headers=auth(token),
        )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
    delay.assert_called_once_with("alice", "Ship feature")


def test_update_task_not_completed_does_not_trigger_notification(client):
    token = register_and_login(client)
    created = client.post(
        "/tasks", json={"title": "Keep working"}, headers=auth(token)
    ).get_json()
    with mock.patch.object(task_app.send_notification_email, "delay") as delay:
        resp = client.put(
            f"/tasks/{created['id']}",
            json={"status": "in_progress"},
            headers=auth(token),
        )
    assert resp.status_code == 200
    delay.assert_not_called()


def test_completing_already_completed_task_does_not_retrigger(client):
    token = register_and_login(client)
    created = client.post(
        "/tasks", json={"title": "Done deal"}, headers=auth(token)
    ).get_json()
    with mock.patch.object(task_app.send_notification_email, "delay") as delay:
        client.put(
            f"/tasks/{created['id']}",
            json={"status": "completed"},
            headers=auth(token),
        )
        delay.reset_mock()
        resp = client.put(
            f"/tasks/{created['id']}",
            json={"status": "completed"},
            headers=auth(token),
        )
    assert resp.status_code == 200
    delay.assert_not_called()


def test_update_task_not_found_does_not_trigger_notification(client):
    token = register_and_login(client)
    with mock.patch.object(task_app.send_notification_email, "delay") as delay:
        resp = client.put(
            "/tasks/9999",
            json={"status": "completed"},
            headers=auth(token),
        )
    assert resp.status_code == 404
    delay.assert_not_called()


def test_update_task_partial(client):
    token = register_and_login(client)
    created = client.post(
        "/tasks", json={"title": "Keep me"}, headers=auth(token)
    ).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"status": "in_progress"},
        headers=auth(token),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Keep me"
    assert data["status"] == "in_progress"


def test_update_task_not_found(client):
    token = register_and_login(client)
    resp = client.put(
        "/tasks/9999", json={"title": "nope"}, headers=auth(token)
    )
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "task not found"}


# ── Ownership isolation ─────────────────────────────────────────


def test_users_see_only_their_own_tasks(client):
    alice_token = register_and_login(client, username="alice")
    bob_token = register_and_login(client, username="bob")

    alice_task = client.post(
        "/tasks", json={"title": "Alice's task"}, headers=auth(alice_token)
    ).get_json()
    client.post(
        "/tasks", json={"title": "Bob's task"}, headers=auth(bob_token)
    )

    alice_list = client.get("/tasks", headers=auth(alice_token)).get_json()
    assert [t["title"] for t in alice_list] == ["Alice's task"]

    bob_list = client.get("/tasks", headers=auth(bob_token)).get_json()
    assert [t["title"] for t in bob_list] == ["Bob's task"]

    assert (
        client.get(f"/tasks/{alice_task['id']}", headers=auth(bob_token)).status_code
        == 404
    )
    resp = client.put(
        f"/tasks/{alice_task['id']}",
        json={"title": "hacked"},
        headers=auth(bob_token),
    )
    assert resp.status_code == 404
