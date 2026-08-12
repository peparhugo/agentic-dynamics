import os
import time

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE", str(tmp_path / "test.db"))
    import importlib
    import app as app_module

    app_module = importlib.reload(app_module)
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


@pytest.fixture()
def auth(client):
    def register(username="alice", password="secret123"):
        return client.post("/auth/register", json={"username": username, "password": password})

    def login(username="alice", password="secret123"):
        return client.post("/auth/login", json={"username": username, "password": password})

    def token(username="alice", password="secret123"):
        rv = login(username, password)
        assert rv.status_code == 200
        return rv.get_json()["token"]

    def headers(username="alice", password="secret123"):
        return {"Authorization": f"Bearer {token(username, password)}"}

    register()
    return {
        "register": register,
        "login": login,
        "token": token,
        "headers": headers,
    }


def post_task(client, title, username="alice", password="secret123"):
    return client.post(
        "/tasks",
        json={"title": title},
        headers={"Authorization": f"Bearer {auth_token(client, username, password)}"},
    )


def auth_token(client, username, password):
    rv = client.post("/auth/login", json={"username": username, "password": password})
    assert rv.status_code == 200
    return rv.get_json()["token"]


# ── Auth: register ────────────────────────────────────────────

def test_register_creates_user(client):
    rv = client.post("/auth/register", json={"username": "bob", "password": "hunter2"})
    assert rv.status_code == 201
    data = rv.get_json()
    assert data["id"] > 0
    assert data["username"] == "bob"
    assert "password_hash" not in data


def test_register_missing_fields_returns_400(client):
    rv = client.post("/auth/register", json={})
    assert rv.status_code == 400
    rv = client.post("/auth/register", json={"username": "bob"})
    assert rv.status_code == 400
    rv = client.post("/auth/register", json={"username": "   ", "password": "x"})
    assert rv.status_code == 400


def test_register_duplicate_username_returns_409(client, auth):
    rv = auth["register"]()
    assert rv.status_code == 409


# ── Auth: login ───────────────────────────────────────────────

def test_login_returns_token(client, auth):
    rv = auth["login"]()
    assert rv.status_code == 200
    token = rv.get_json()["token"]
    assert isinstance(token, str) and token


def test_login_wrong_password_returns_401(client, auth):
    rv = client.post("/auth/login", json={"username": "alice", "password": "wrong"})
    assert rv.status_code == 401


def test_login_unknown_user_returns_401(client):
    rv = client.post("/auth/login", json={"username": "nobody", "password": "x"})
    assert rv.status_code == 401


def test_passwords_are_hashed(client, auth):
    import app as app_module

    with app_module.get_db() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE username = 'alice'").fetchone()
    assert row is not None
    assert row["password_hash"] != "secret123"
    assert row["password_hash"].startswith("$2")


# ── Auth: protection ──────────────────────────────────────────

def test_tasks_require_token(client):
    rv = client.get("/tasks")
    assert rv.status_code == 401
    rv = client.post("/tasks", json={"title": "x"})
    assert rv.status_code == 401
    rv = client.get("/tasks/1")
    assert rv.status_code == 401
    rv = client.put("/tasks/1", json={"status": "done"})
    assert rv.status_code == 401


def test_tasks_reject_invalid_token(client):
    headers = {"Authorization": "Bearer not.a.token"}
    rv = client.get("/tasks", headers=headers)
    assert rv.status_code == 401


def test_tasks_reject_garbage_header(client):
    rv = client.get("/tasks", headers={"Authorization": "Basic abc123"})
    assert rv.status_code == 401


# ── Tasks (existing behavior, now authenticated) ─────────────

def test_create_task(client, auth):
    rv = post_task(client, "Write code")
    assert rv.status_code == 201
    data = rv.get_json()
    assert data["id"] > 0
    assert data["title"] == "Write code"
    assert data["status"] == "pending"
    assert isinstance(data["created_at"], int)


def test_create_task_missing_title_returns_400(client, auth):
    rv = client.post("/tasks", json={}, headers=auth["headers"]())
    assert rv.status_code == 400
    assert "error" in rv.get_json()

    rv = client.post("/tasks", json={"title": "   "}, headers=auth["headers"]())
    assert rv.status_code == 400


def test_list_tasks_ordered_by_created_at_desc(client, auth):
    post_task(client, "first")
    time.sleep(1.1)
    post_task(client, "second")
    time.sleep(1.1)
    post_task(client, "third")

    rv = client.get("/tasks", headers=auth["headers"]())
    assert rv.status_code == 200
    tasks = rv.get_json()
    assert [t["title"] for t in tasks] == ["third", "second", "first"]
    assert [t["created_at"] for t in tasks] == sorted(
        (t["created_at"] for t in tasks), reverse=True
    )


def test_get_task(client, auth):
    created = post_task(client, "Fetch me").get_json()
    rv = client.get(f"/tasks/{created['id']}", headers=auth["headers"]())
    assert rv.status_code == 200
    assert rv.get_json() == created


def test_get_task_not_found_returns_404(client, auth):
    rv = client.get("/tasks/9999", headers=auth["headers"]())
    assert rv.status_code == 404
    assert "error" in rv.get_json()


def test_update_task_title_and_status(client, auth):
    created = post_task(client, "Original").get_json()
    tid = created["id"]

    rv = client.put(
        f"/tasks/{tid}",
        json={"title": "Updated", "status": "done"},
        headers=auth["headers"](),
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["title"] == "Updated"
    assert data["status"] == "done"

    rv = client.put(f"/tasks/{tid}", json={"title": "Only title"}, headers=auth["headers"]())
    assert rv.get_json()["title"] == "Only title"
    assert rv.get_json()["status"] == "done"

    rv = client.put(f"/tasks/{tid}", json={"status": "in_progress"}, headers=auth["headers"]())
    assert rv.get_json()["status"] == "in_progress"
    assert rv.get_json()["title"] == "Only title"


def test_update_task_not_found_returns_404(client, auth):
    rv = client.put("/tasks/9999", json={"status": "done"}, headers=auth["headers"]())
    assert rv.status_code == 404
    assert "error" in rv.get_json()


# ── Per-user isolation ────────────────────────────────────────

def test_users_only_see_their_own_tasks(client, auth):
    auth["register"]("bob", "bobpass")
    bob_headers = auth["headers"]("bob", "bobpass")
    alice_headers = auth["headers"]()

    post_task(client, "alice task")
    rv = client.post("/tasks", json={"title": "bob task"}, headers=bob_headers)
    assert rv.status_code == 201

    alice_tasks = client.get("/tasks", headers=alice_headers).get_json()
    bob_tasks = client.get("/tasks", headers=bob_headers).get_json()
    assert [t["title"] for t in alice_tasks] == ["alice task"]
    assert [t["title"] for t in bob_tasks] == ["bob task"]


def test_user_cannot_read_another_users_task(client, auth):
    auth["register"]("bob", "bobpass")
    created = post_task(client, "secret").get_json()

    rv = client.get(f"/tasks/{created['id']}", headers=auth["headers"]("bob", "bobpass"))
    assert rv.status_code == 404


def test_user_cannot_update_another_users_task(client, auth):
    auth["register"]("bob", "bobpass")
    created = post_task(client, "secret").get_json()

    rv = client.put(
        f"/tasks/{created['id']}",
        json={"status": "done"},
        headers=auth["headers"]("bob", "bobpass"),
    )
    assert rv.status_code == 404
