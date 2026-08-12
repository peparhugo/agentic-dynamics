import os
import tempfile
import pytest

DATABASE = os.environ.get("TEST_DATABASE")

if DATABASE is None:
    _tmpdir = tempfile.mkdtemp()
    DATABASE = os.path.join(_tmpdir, "test_todos.db")

os.environ["DATABASE"] = DATABASE

import app as app_module

app_module.DATABASE = DATABASE
app_module.init_db()


@pytest.fixture(autouse=True)
def clean_db():
    yield
    with app_module.get_db() as conn:
        conn.execute("DELETE FROM tasks")
        conn.execute("DELETE FROM users")
        conn.commit()


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def register(client, username="alice", password="secret"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="secret"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_headers(client, username="alice", password="secret"):
    token = login(client, username, password).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ── Auth tests ────────────────────────────────────────────────


def test_register(client):
    resp = register(client)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] > 0
    assert data["username"] == "alice"
    assert "password" not in data
    assert "password_hash" not in data


def test_register_requires_fields(client):
    resp = client.post("/auth/register", json={"username": "bob"})
    assert resp.status_code == 400
    resp = client.post("/auth/register", json={"password": "secret"})
    assert resp.status_code == 400
    resp = client.post("/auth/register", json={})
    assert resp.status_code == 400


def test_register_duplicate_username(client):
    register(client)
    resp = register(client)
    assert resp.status_code == 400
    assert resp.get_json()["error"]


def test_login_returns_token(client):
    register(client)
    resp = login(client)
    assert resp.status_code == 200
    assert resp.get_json()["token"]


def test_login_wrong_password(client):
    register(client)
    resp = login(client, password="wrong")
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = login(client, username="nobody")
    assert resp.status_code == 401


def test_tasks_require_auth(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
    resp = client.post("/tasks", json={"title": "x"})
    assert resp.status_code == 401
    resp = client.get("/tasks/1")
    assert resp.status_code == 401
    resp = client.put("/tasks/1", json={"title": "x"})
    assert resp.status_code == 401


def test_tasks_reject_invalid_token(client):
    headers = {"Authorization": "Bearer not.a.valid.token"}
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 401
    resp = client.post("/tasks", json={"title": "x"}, headers=headers)
    assert resp.status_code == 401


def test_tasks_reject_malformed_header(client):
    headers = {"Authorization": "Token abc123"}
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 401


# ── Task tests (authenticated) ────────────────────────────────


def test_create_task(client):
    register(client)
    resp = client.post("/tasks", json={"title": "buy milk"}, headers=auth_headers(client))
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] > 0
    assert data["title"] == "buy milk"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_create_task_requires_title(client):
    register(client)
    headers = auth_headers(client)
    resp = client.post("/tasks", json={}, headers=headers)
    assert resp.status_code == 400
    assert resp.get_json()["error"]


def test_create_task_rejects_blank_title(client):
    register(client)
    headers = auth_headers(client)
    resp = client.post("/tasks", json={"title": "   "}, headers=headers)
    assert resp.status_code == 400


def test_list_tasks_ordered_desc(client):
    register(client)
    headers = auth_headers(client)
    client.post("/tasks", json={"title": "first"}, headers=headers)
    client.post("/tasks", json={"title": "second"}, headers=headers)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    tasks = resp.get_json()
    assert [t["title"] for t in tasks] == ["second", "first"]


def test_list_tasks_only_own(client):
    register(client, username="alice")
    register(client, username="bob")
    alice = auth_headers(client, username="alice")
    bob = auth_headers(client, username="bob")
    client.post("/tasks", json={"title": "alice task"}, headers=alice)
    client.post("/tasks", json={"title": "bob task"}, headers=bob)

    resp = client.get("/tasks", headers=alice)
    assert [t["title"] for t in resp.get_json()] == ["alice task"]
    resp = client.get("/tasks", headers=bob)
    assert [t["title"] for t in resp.get_json()] == ["bob task"]


def test_get_task(client):
    register(client)
    headers = auth_headers(client)
    created = client.post("/tasks", json={"title": "hello"}, headers=headers).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "hello"


def test_get_task_not_found(client):
    register(client)
    headers = auth_headers(client)
    resp = client.get("/tasks/999", headers=headers)
    assert resp.status_code == 404
    assert resp.get_json()["error"]


def test_get_other_users_task_not_found(client):
    register(client, username="alice")
    register(client, username="bob")
    alice = auth_headers(client, username="alice")
    bob = auth_headers(client, username="bob")
    created = client.post("/tasks", json={"title": "private"}, headers=alice).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=bob)
    assert resp.status_code == 404


def test_update_task_title(client):
    register(client)
    headers = auth_headers(client)
    created = client.post("/tasks", json={"title": "old"}, headers=headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "new"}, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "new"
    assert data["status"] == "pending"


def test_update_task_status(client):
    register(client)
    headers = auth_headers(client)
    created = client.post("/tasks", json={"title": "task"}, headers=headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"}, headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "done"


def test_update_task_both(client):
    register(client)
    headers = auth_headers(client)
    created = client.post("/tasks", json={"title": "a"}, headers=headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "b", "status": "in_progress"},
        headers=headers,
    )
    data = resp.get_json()
    assert data["title"] == "b"
    assert data["status"] == "in_progress"


def test_update_task_not_found(client):
    register(client)
    headers = auth_headers(client)
    resp = client.put("/tasks/999", json={"title": "x"}, headers=headers)
    assert resp.status_code == 404
    assert resp.get_json()["error"]


def test_update_other_users_task_not_found(client):
    register(client, username="alice")
    register(client, username="bob")
    alice = auth_headers(client, username="alice")
    bob = auth_headers(client, username="bob")
    created = client.post("/tasks", json={"title": "private"}, headers=alice).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "hacked"}, headers=bob)
    assert resp.status_code == 404
