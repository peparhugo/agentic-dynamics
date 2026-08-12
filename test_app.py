import os
import tempfile

import pytest

from app import app, init_db


@pytest.fixture()
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    app.config.update(TESTING=True)

    import app as app_module
    app_module.DATABASE = path
    init_db()

    with app.test_client() as c:
        yield c

    os.unlink(path)


def register(client, username="alice", password="secret"):
    return client.post(
        "/auth/register", json={"username": username, "password": password}
    )


def login(client, username="alice", password="secret"):
    return client.post(
        "/auth/login", json={"username": username, "password": password}
    )


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def token(client):
    register(client)
    return login(client).get_json()["token"]


@pytest.fixture()
def auth(client, token):
    return auth_headers(token)


def test_create_task(client, auth):
    res = client.post("/tasks", json={"title": "write code"}, headers=auth)
    assert res.status_code == 201
    body = res.get_json()
    assert body["title"] == "write code"
    assert body["status"] == "pending"
    assert body["id"] == 1
    assert body["created_at"]


def test_create_task_missing_title(client, auth):
    res = client.post("/tasks", json={}, headers=auth)
    assert res.status_code == 400
    assert res.get_json()["error"]


def test_create_task_empty_title(client, auth):
    res = client.post("/tasks", json={"title": "   "}, headers=auth)
    assert res.status_code == 400
    assert res.get_json()["error"]


def test_create_task_no_json(client, auth):
    res = client.post("/tasks", data="not json", headers=auth)
    assert res.status_code == 400
    assert res.get_json()["error"]


def test_list_tasks_ordered_desc(client, auth):
    client.post("/tasks", json={"title": "first"}, headers=auth)
    client.post("/tasks", json={"title": "second"}, headers=auth)
    res = client.get("/tasks", headers=auth)
    assert res.status_code == 200
    tasks = res.get_json()
    assert len(tasks) == 2
    assert tasks[0]["title"] == "second"
    assert tasks[1]["title"] == "first"


def test_get_task(client, auth):
    created = client.post("/tasks", json={"title": "hello"}, headers=auth).get_json()
    res = client.get(f"/tasks/{created['id']}", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["title"] == "hello"


def test_get_task_not_found(client, auth):
    res = client.get("/tasks/999", headers=auth)
    assert res.status_code == 404
    assert res.get_json()["error"]


def test_update_task_title_and_status(client, auth):
    created = client.post("/tasks", json={"title": "hello"}, headers=auth).get_json()
    res = client.put(
        f"/tasks/{created['id']}",
        json={"title": "updated", "status": "done"},
        headers=auth,
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["title"] == "updated"
    assert body["status"] == "done"


def test_update_task_not_found(client, auth):
    res = client.put("/tasks/999", json={"title": "x"}, headers=auth)
    assert res.status_code == 404
    assert res.get_json()["error"]


def test_update_task_partial(client, auth):
    created = client.post("/tasks", json={"title": "hello"}, headers=auth).get_json()
    res = client.put(
        f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=auth
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["title"] == "hello"
    assert body["status"] == "in_progress"


def test_register_creates_user(client):
    res = register(client)
    assert res.status_code == 201
    body = res.get_json()
    assert body["username"] == "alice"
    assert "password" not in body


def test_register_duplicate_username(client):
    register(client)
    res = register(client)
    assert res.status_code == 409
    assert res.get_json()["error"]


def test_register_missing_username(client):
    res = client.post("/auth/register", json={"password": "secret"})
    assert res.status_code == 400
    assert res.get_json()["error"]


def test_register_missing_password(client):
    res = client.post("/auth/register", json={"username": "alice"})
    assert res.status_code == 400
    assert res.get_json()["error"]


def test_login_returns_token(client):
    register(client)
    res = login(client)
    assert res.status_code == 200
    body = res.get_json()
    assert body["token"]
    assert body["username"] == "alice"


def test_login_wrong_password(client):
    register(client)
    res = login(client, password="wrong")
    assert res.status_code == 401
    assert res.get_json()["error"]


def test_login_unknown_user(client):
    res = login(client, username="nobody")
    assert res.status_code == 401
    assert res.get_json()["error"]


def test_tasks_require_token(client):
    res = client.get("/tasks")
    assert res.status_code == 401
    res = client.post("/tasks", json={"title": "x"})
    assert res.status_code == 401


def test_tasks_invalid_token(client):
    headers = auth_headers("not-a-valid-token")
    res = client.get("/tasks", headers=headers)
    assert res.status_code == 401
    assert res.get_json()["error"]


def test_tasks_missing_bearer_scheme(client, token):
    res = client.get("/tasks", headers={"Authorization": token})
    assert res.status_code == 401
    assert res.get_json()["error"]


def test_user_sees_only_own_tasks(client):
    register(client, "alice")
    register(client, "bob")
    alice_token = login(client, "alice").get_json()["token"]
    bob_token = login(client, "bob").get_json()["token"]

    created = client.post(
        "/tasks",
        json={"title": "alice task"},
        headers=auth_headers(alice_token),
    ).get_json()

    bob_tasks = client.get("/tasks", headers=auth_headers(bob_token)).get_json()
    assert bob_tasks == []

    res = client.get(
        f"/tasks/{created['id']}", headers=auth_headers(bob_token)
    )
    assert res.status_code == 404

    res = client.put(
        f"/tasks/{created['id']}",
        json={"status": "done"},
        headers=auth_headers(bob_token),
    )
    assert res.status_code == 404

    alice_tasks = client.get("/tasks", headers=auth_headers(alice_token)).get_json()
    assert [t["id"] for t in alice_tasks] == [created["id"]]
