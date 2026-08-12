import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

import app as app_module


@pytest.fixture()
def client(tmp_path):
    app_module.app.config["TESTING"] = True
    app_module.app.config["SECRET_KEY"] = "test-secret-key"
    app_module.app.config["DATABASE"] = str(tmp_path / "test_tasks.db")
    app_module.init_db()
    with app_module.app.test_client() as client:
        yield client


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def register(client, username="alice", password="secret"):
    resp = client.post(
        "/auth/register", json={"username": username, "password": password}
    )
    assert resp.status_code == 201, resp.get_json()
    return resp


def login(client, username="alice", password="secret"):
    resp = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()["token"]


@pytest.fixture()
def alice(client):
    register(client, "alice", "alice-pass")
    return login(client, "alice", "alice-pass")


@pytest.fixture()
def bob(client):
    register(client, "bob", "bob-pass")
    return login(client, "bob", "bob-pass")


def test_register_creates_user(client):
    resp = register(client, "carol", "carol-pass")
    data = resp.get_json()
    assert data["id"] == 1
    assert data["username"] == "carol"
    assert "password_hash" not in data


def test_register_duplicate_username(client):
    register(client, "carol", "pass1")
    resp = client.post(
        "/auth/register", json={"username": "carol", "password": "pass2"}
    )
    assert resp.status_code == 409
    assert "error" in resp.get_json()


def test_register_missing_fields(client):
    resp = client.post("/auth/register", json={})
    assert resp.status_code == 400

    resp = client.post("/auth/register", json={"username": "x"})
    assert resp.status_code == 400

    resp = client.post("/auth/register", json={"password": "x"})
    assert resp.status_code == 400


def test_login_returns_token(client):
    register(client, "dave", "dave-pass")
    resp = client.post(
        "/auth/login", json={"username": "dave", "password": "dave-pass"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data
    assert data["user"]["username"] == "dave"


def test_login_wrong_credentials(client):
    register(client, "dave", "dave-pass")
    resp = client.post(
        "/auth/login", json={"username": "dave", "password": "wrong"}
    )
    assert resp.status_code == 401

    resp = client.post(
        "/auth/login", json={"username": "nobody", "password": "wrong"}
    )
    assert resp.status_code == 401


def test_tasks_require_auth(client):
    assert client.post("/tasks", json={"title": "x"}).status_code == 401
    assert client.get("/tasks").status_code == 401
    assert client.get("/tasks/1").status_code == 401
    assert client.put("/tasks/1", json={"title": "x"}).status_code == 401


def test_tasks_invalid_token(client):
    bad_headers = [
        {"Authorization": "Bearer not-a-real-token"},
        {"Authorization": "Bearer "},
        {"Authorization": "Basic abc"},
    ]
    for headers in bad_headers:
        assert client.get("/tasks", headers=headers).status_code == 401


def test_create_task(client, alice):
    resp = client.post(
        "/tasks", json={"title": "write docs"}, headers=auth_headers(alice)
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "write docs"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_create_task_missing_title(client, alice):
    resp = client.post("/tasks", json={}, headers=auth_headers(alice))
    assert resp.status_code == 400
    assert "error" in resp.get_json()

    resp = client.post("/tasks", json={"title": ""}, headers=auth_headers(alice))
    assert resp.status_code == 400

    resp = client.post(
        "/tasks", data="not json", content_type="text/plain", headers=auth_headers(alice)
    )
    assert resp.status_code == 400


def test_list_tasks_ordered_desc(client, alice):
    client.post("/tasks", json={"title": "first"}, headers=auth_headers(alice))
    client.post("/tasks", json={"title": "second"}, headers=auth_headers(alice))
    client.post("/tasks", json={"title": "third"}, headers=auth_headers(alice))
    resp = client.get("/tasks", headers=auth_headers(alice))
    assert resp.status_code == 200
    tasks = resp.get_json()
    assert [t["title"] for t in tasks] == ["third", "second", "first"]
    assert [t["id"] for t in tasks] == [3, 2, 1]


def test_get_task(client, alice):
    created = client.post(
        "/tasks", json={"title": "read"}, headers=auth_headers(alice)
    )
    task_id = created.get_json()["id"]
    resp = client.get(f"/tasks/{task_id}", headers=auth_headers(alice))
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "read"


def test_get_task_not_found(client, alice):
    resp = client.get("/tasks/999", headers=auth_headers(alice))
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task(client, alice):
    created = client.post(
        "/tasks", json={"title": "old"}, headers=auth_headers(alice)
    )
    task_id = created.get_json()["id"]

    resp = client.put(
        f"/tasks/{task_id}",
        json={"title": "new", "status": "done"},
        headers=auth_headers(alice),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "new"
    assert data["status"] == "done"

    resp = client.put(
        f"/tasks/{task_id}",
        json={"status": "in_progress"},
        headers=auth_headers(alice),
    )
    data = resp.get_json()
    assert data["title"] == "new"
    assert data["status"] == "in_progress"


def test_update_task_not_found(client, alice):
    resp = client.put(
        "/tasks/999", json={"title": "x"}, headers=auth_headers(alice)
    )
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_users_see_only_their_own_tasks(client, alice, bob):
    client.post("/tasks", json={"title": "alice task"}, headers=auth_headers(alice))
    client.post("/tasks", json={"title": "bob task"}, headers=auth_headers(bob))

    alice_tasks = client.get("/tasks", headers=auth_headers(alice)).get_json()
    assert [t["title"] for t in alice_tasks] == ["alice task"]

    bob_tasks = client.get("/tasks", headers=auth_headers(bob)).get_json()
    assert [t["title"] for t in bob_tasks] == ["bob task"]


def test_cannot_access_others_task(client, alice, bob):
    created = client.post(
        "/tasks", json={"title": "alice task"}, headers=auth_headers(alice)
    )
    task_id = created.get_json()["id"]

    assert client.get(f"/tasks/{task_id}", headers=auth_headers(bob)).status_code == 404
    assert (
        client.put(
            f"/tasks/{task_id}", json={"title": "hijacked"}, headers=auth_headers(bob)
        ).status_code
        == 404
    )

    after = client.get(f"/tasks/{task_id}", headers=auth_headers(alice))
    assert after.get_json()["title"] == "alice task"


class FakeCeleryTask:
    def __init__(self):
        self.calls = []

    def delay(self, *args, **kwargs):
        self.calls.append((args, kwargs))


def test_celery_config_present():
    import celery_config

    assert celery_config.broker_url
    assert celery_config.result_backend
    assert isinstance(celery_config.task_routes, dict)


def test_send_notification_email_task_registered():
    assert app_module.send_notification_email.name == "app.send_notification_email"
    assert app_module.send_notification_email.__name__ == "send_notification_email"


def test_send_notification_email_task_body(capsys):
    app_module.send_notification_email("alice@example.com", "Write docs")
    captured = capsys.readouterr()
    assert "alice@example.com" in captured.out
    assert "Write docs" in captured.out


def test_completing_task_triggers_notification(monkeypatch, client, alice):
    created = client.post(
        "/tasks", json={"title": "ship it"}, headers=auth_headers(alice)
    )
    task_id = created.get_json()["id"]

    fake = FakeCeleryTask()
    monkeypatch.setattr(app_module, "send_notification_email", fake)

    resp = client.put(
        f"/tasks/{task_id}",
        json={"status": "completed"},
        headers=auth_headers(alice),
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
    assert fake.calls == [(("alice", "ship it"), {})]


def test_no_notification_unless_completed(monkeypatch, client, alice):
    created = client.post(
        "/tasks", json={"title": "docs"}, headers=auth_headers(alice)
    )
    task_id = created.get_json()["id"]

    fake = FakeCeleryTask()
    monkeypatch.setattr(app_module, "send_notification_email", fake)

    resp = client.put(
        f"/tasks/{task_id}", json={"title": "renamed"}, headers=auth_headers(alice)
    )
    assert resp.status_code == 200
    assert fake.calls == []

    client.put(
        f"/tasks/{task_id}", json={"status": "in_progress"}, headers=auth_headers(alice)
    )
    assert fake.calls == []

    client.put(
        f"/tasks/{task_id}", json={"status": "done"}, headers=auth_headers(alice)
    )
    assert fake.calls == []


def test_completion_transition_triggers_once(monkeypatch, client, alice):
    created = client.post(
        "/tasks", json={"title": "release"}, headers=auth_headers(alice)
    )
    task_id = created.get_json()["id"]

    fake = FakeCeleryTask()
    monkeypatch.setattr(app_module, "send_notification_email", fake)

    client.put(
        f"/tasks/{task_id}",
        json={"title": "release v2", "status": "completed"},
        headers=auth_headers(alice),
    )
    assert fake.calls == [(("alice", "release v2"), {})]

    client.put(
        f"/tasks/{task_id}",
        json={"status": "completed"},
        headers=auth_headers(alice),
    )
    assert len(fake.calls) == 1


def test_completed_task_returns_quickly_without_broker(client, alice, monkeypatch):
    created = client.post(
        "/tasks", json={"title": "offline"}, headers=auth_headers(alice)
    )
    task_id = created.get_json()["id"]

    def broken_delay(*args, **kwargs):
        raise RuntimeError("broker unreachable")

    monkeypatch.setattr(app_module.send_notification_email, "delay", broken_delay)

    resp = client.put(
        f"/tasks/{task_id}",
        json={"status": "completed"},
        headers=auth_headers(alice),
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
