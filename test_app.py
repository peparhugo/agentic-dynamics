import time

import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE", str(db_path))
    import app as app_module

    app_module.DATABASE = str(db_path)
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def register(client, username="alice", password="secret"):
    return client.post(
        "/auth/register", json={"username": username, "password": password}
    )


def login(client, username="alice", password="secret"):
    return client.post(
        "/auth/login", json={"username": username, "password": password}
    )


def auth_headers(client, username="alice", password="secret"):
    register(client, username, password)
    resp = login(client, username, password)
    assert resp.status_code == 200
    return {"Authorization": "Bearer " + resp.get_json()["token"]}


def test_register(client):
    resp = register(client)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "alice"
    assert data["id"] == 1


def test_register_duplicate(client):
    assert register(client).status_code == 201
    resp = register(client)
    assert resp.status_code == 409


def test_register_missing_password(client):
    resp = client.post("/auth/register", json={"username": "alice"})
    assert resp.status_code == 400


def test_login_returns_token(client):
    register(client)
    resp = login(client)
    assert resp.status_code == 200
    assert "token" in resp.get_json()


def test_login_wrong_password(client):
    register(client)
    resp = login(client, password="wrong")
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = login(client, username="ghost")
    assert resp.status_code == 401


def test_tasks_require_auth(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "x"}).status_code == 401
    assert client.get("/tasks/1").status_code == 401
    assert client.put("/tasks/1", json={"title": "x"}).status_code == 401


def test_tasks_reject_invalid_token(client):
    resp = client.get("/tasks", headers={"Authorization": "Bearer bogus"})
    assert resp.status_code == 401


def test_create_task(client):
    headers = auth_headers(client)
    resp = client.post("/tasks", json={"title": "first task"}, headers=headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "first task"
    assert data["status"] == "pending"
    assert isinstance(data["created_at"], int)
    assert data["id"] == 1


def test_create_task_missing_title(client):
    headers = auth_headers(client)
    resp = client.post("/tasks", json={}, headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_ordered_desc(client):
    headers = auth_headers(client)
    client.post("/tasks", json={"title": "a"}, headers=headers)
    time.sleep(1.1)
    client.post("/tasks", json={"title": "b"}, headers=headers)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert [t["title"] for t in data] == ["b", "a"]


def test_get_task(client):
    headers = auth_headers(client)
    client.post("/tasks", json={"title": "single"}, headers=headers)
    resp = client.get("/tasks/1", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "single"


def test_get_task_not_found(client):
    headers = auth_headers(client)
    resp = client.get("/tasks/999", headers=headers)
    assert resp.status_code == 404


def test_update_task(client):
    headers = auth_headers(client)
    client.post("/tasks", json={"title": "old"}, headers=headers)
    resp = client.put(
        "/tasks/1", json={"title": "new", "status": "done"}, headers=headers
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "new"
    assert data["status"] == "done"


def test_update_task_not_found(client):
    headers = auth_headers(client)
    resp = client.put("/tasks/999", json={"title": "x"}, headers=headers)
    assert resp.status_code == 404


def test_users_only_see_their_own_tasks(client):
    alice = auth_headers(client, "alice", "pw1")
    bob = auth_headers(client, "bob", "pw2")
    client.post("/tasks", json={"title": "alice task"}, headers=alice)
    client.post("/tasks", json={"title": "bob task"}, headers=bob)

    resp = client.get("/tasks", headers=alice)
    assert resp.status_code == 200
    assert [t["title"] for t in resp.get_json()] == ["alice task"]

    resp = client.get("/tasks", headers=bob)
    assert [t["title"] for t in resp.get_json()] == ["bob task"]

    assert client.get("/tasks/2", headers=alice).status_code == 404
    assert client.get("/tasks/2", headers=bob).status_code == 200


def test_completing_task_triggers_notification_email(client, monkeypatch):
    import app as app_module

    sent = []
    monkeypatch.setattr(
        app_module.send_notification_email,
        "delay",
        lambda user_email, task_title: sent.append((user_email, task_title)),
    )

    headers = auth_headers(client)
    client.post("/tasks", json={"title": "notify me"}, headers=headers)
    resp = client.put("/tasks/1", json={"status": "completed"}, headers=headers)

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
    assert sent == [("alice@example.com", "notify me")]


def test_non_completed_status_does_not_trigger_notification(client, monkeypatch):
    import app as app_module

    sent = []
    monkeypatch.setattr(
        app_module.send_notification_email,
        "delay",
        lambda user_email, task_title: sent.append((user_email, task_title)),
    )

    headers = auth_headers(client)
    client.post("/tasks", json={"title": "keep pending"}, headers=headers)
    resp = client.put("/tasks/1", json={"status": "done"}, headers=headers)

    assert resp.status_code == 200
    assert sent == []


def test_already_completed_task_does_not_re_notify(client, monkeypatch):
    import app as app_module

    sent = []
    monkeypatch.setattr(
        app_module.send_notification_email,
        "delay",
        lambda user_email, task_title: sent.append((user_email, task_title)),
    )

    headers = auth_headers(client)
    client.post("/tasks", json={"title": "done once"}, headers=headers)
    client.put("/tasks/1", json={"status": "completed"}, headers=headers)
    assert sent == [("alice@example.com", "done once")]

    client.put("/tasks/1", json={"status": "completed"}, headers=headers)
    assert sent == [("alice@example.com", "done once")]


def test_notification_uses_registered_email(client, monkeypatch):
    import app as app_module

    sent = []
    monkeypatch.setattr(
        app_module.send_notification_email,
        "delay",
        lambda user_email, task_title: sent.append((user_email, task_title)),
    )

    client.post(
        "/auth/register",
        json={"username": "carol", "password": "pw", "email": "carol@corp.com"},
    )
    resp = client.post(
        "/auth/login", json={"username": "carol", "password": "pw"}
    )
    headers = {"Authorization": "Bearer " + resp.get_json()["token"]}

    client.post("/tasks", json={"title": "email me"}, headers=headers)
    resp = client.put("/tasks/1", json={"status": "completed"}, headers=headers)

    assert resp.status_code == 200
    assert sent == [("carol@corp.com", "email me")]
