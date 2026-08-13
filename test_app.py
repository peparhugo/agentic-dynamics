import os
import time

import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "test_todos.db"
    app_module.DATABASE = str(db_path)
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client


def _register(client, username="alice", password="hunter2"):
    return client.post("/auth/register", json={"username": username, "password": password})


def _login(client, username="alice", password="hunter2"):
    return client.post("/auth/login", json={"username": username, "password": password})


def _auth_headers(client, username="alice", password="hunter2"):
    _register(client, username, password)
    token = _login(client, username, password).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _create(client, title="Buy milk", headers=None):
    if headers is None:
        headers = _auth_headers(client)
    return client.post("/tasks", json={"title": title}, headers=headers)


# ── POST /auth/register ─────────────────────────────────────────


def test_register_returns_201_and_user(client):
    resp = _register(client, "bob", "secret123")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["username"] == "bob"
    assert isinstance(body["id"], int)
    assert "password" not in body
    assert "password_hash" not in body


def test_register_duplicate_username_returns_400(client):
    _register(client, "bob", "secret123")
    resp = _register(client, "bob", "different")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_missing_username_returns_400(client):
    resp = client.post("/auth/register", json={"password": "secret123"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_missing_password_returns_400(client):
    resp = client.post("/auth/register", json={"username": "bob"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_password_is_hashed(client):
    _register(client, "bob", "secret123")
    user = app_module.get_user_by_username("bob")
    assert user["password_hash"] != "secret123"


# ── POST /auth/login ─────────────────────────────────────────────


def test_login_returns_token(client):
    _register(client, "bob", "secret123")
    resp = _login(client, "bob", "secret123")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "token" in body
    assert isinstance(body["token"], str)


def test_login_wrong_password_returns_401(client):
    _register(client, "bob", "secret123")
    resp = _login(client, "bob", "wrong")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_nonexistent_user_returns_401(client):
    resp = _login(client, "ghost", "whatever")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


# ── Auth protection on /tasks ────────────────────────────────────


def test_tasks_without_token_returns_401(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_tasks_with_invalid_token_returns_401(client):
    resp = client.get("/tasks", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_tasks_with_malformed_header_returns_401(client):
    resp = client.get("/tasks", headers={"Authorization": "not-bearer-token"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_create_task_without_token_returns_401(client):
    resp = client.post("/tasks", json={"title": "nope"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


# ── POST /tasks ──────────────────────────────────────────────


def test_create_task_returns_201_and_task(client):
    resp = _create(client, "Write report")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["title"] == "Write report"
    assert body["status"] == "pending"
    assert isinstance(body["id"], int)
    assert "created_at" in body


def test_create_task_persists(client):
    headers = _auth_headers(client)
    _create(client, "Persisted task", headers=headers)
    resp = client.get("/tasks", headers=headers)
    titles = [t["title"] for t in resp.get_json()]
    assert "Persisted task" in titles


def test_create_task_missing_title_returns_400(client):
    headers = _auth_headers(client)
    resp = client.post("/tasks", json={}, headers=headers)
    assert resp.status_code == 400
    body = resp.get_json()
    assert "error" in body


def test_create_task_blank_title_returns_400(client):
    headers = _auth_headers(client)
    resp = client.post("/tasks", json={"title": "   "}, headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_no_json_body_returns_400(client):
    headers = _auth_headers(client)
    resp = client.post("/tasks", headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


# ── GET /tasks ───────────────────────────────────────────────


def test_list_tasks_empty(client):
    headers = _auth_headers(client)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_tasks_ordered_desc_by_created_at(client):
    headers = _auth_headers(client)
    _create(client, "first", headers=headers)
    time.sleep(0.01)
    _create(client, "second", headers=headers)
    time.sleep(0.01)
    _create(client, "third", headers=headers)

    resp = client.get("/tasks", headers=headers)
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["third", "second", "first"]


def test_list_tasks_only_shows_own_tasks(client):
    alice_headers = _auth_headers(client, "alice", "pw1")
    bob_headers = _auth_headers(client, "bob", "pw2")

    _create(client, "alice task", headers=alice_headers)
    _create(client, "bob task", headers=bob_headers)

    alice_titles = [t["title"] for t in client.get("/tasks", headers=alice_headers).get_json()]
    bob_titles = [t["title"] for t in client.get("/tasks", headers=bob_headers).get_json()]

    assert alice_titles == ["alice task"]
    assert bob_titles == ["bob task"]


# ── GET /tasks/{id} ──────────────────────────────────────────


def test_get_single_task(client):
    headers = _auth_headers(client)
    created = _create(client, "Find me", headers=headers).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["id"] == created["id"]
    assert body["title"] == "Find me"


def test_get_nonexistent_task_returns_404(client):
    headers = _auth_headers(client)
    resp = client.get("/tasks/9999", headers=headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_get_other_users_task_returns_404(client):
    alice_headers = _auth_headers(client, "alice", "pw1")
    bob_headers = _auth_headers(client, "bob", "pw2")

    created = _create(client, "alice's secret", headers=alice_headers).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=bob_headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


# ── PUT /tasks/{id} ──────────────────────────────────────────


def test_update_title_only(client):
    headers = _auth_headers(client)
    created = _create(client, "old title", headers=headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "new title"}, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "new title"
    assert body["status"] == "pending"


def test_update_status_only(client):
    headers = _auth_headers(client)
    created = _create(client, "keep", headers=headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "keep"
    assert body["status"] == "in_progress"


def test_update_title_and_status(client):
    headers = _auth_headers(client)
    created = _create(client, "keep", headers=headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "changed", "status": "done"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "changed"
    assert body["status"] == "done"


def test_update_nonexistent_task_returns_404(client):
    headers = _auth_headers(client)
    resp = client.put("/tasks/9999", json={"title": "nope"}, headers=headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_other_users_task_returns_404(client):
    alice_headers = _auth_headers(client, "alice", "pw1")
    bob_headers = _auth_headers(client, "bob", "pw2")

    created = _create(client, "alice's task", headers=alice_headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "hijacked"}, headers=bob_headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


# ── Migration ─────────────────────────────────────────────────


def test_migration_adds_owner_id_to_legacy_table(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = app_module.sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE tasks ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  title TEXT NOT NULL,"
        "  status TEXT NOT NULL DEFAULT 'pending',"
        "  created_at TEXT NOT NULL"
        ")"
    )
    conn.execute(
        "INSERT INTO tasks (title, status, created_at) VALUES ('legacy task', 'pending', '2024-01-01T00:00:00')"
    )
    conn.commit()
    conn.close()

    app_module.DATABASE = str(db_path)
    app_module.init_db()

    conn = app_module.get_db()
    row = conn.execute("SELECT * FROM tasks WHERE title = 'legacy task'").fetchone()
    conn.close()
    assert row is not None
    assert row["owner_id"] is None
