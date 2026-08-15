import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path):
    app_module.DATABASE = str(tmp_path / "test.db")
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def register(client, username="alice", password="secret123"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="secret123"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_header(client, username="alice", password="secret123"):
    register(client, username, password)
    token = login(client, username, password).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ── Auth: register ──────────────────────────────────────────────

def test_register_creates_user(client):
    resp = register(client)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["username"] == "alice"
    assert isinstance(body["id"], int)
    assert "password" not in body
    assert "password_hash" not in body


def test_register_missing_username(client):
    resp = client.post("/auth/register", json={"password": "secret123"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_missing_password(client):
    resp = client.post("/auth/register", json={"username": "alice"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_duplicate_username(client):
    register(client)
    resp = register(client)
    assert resp.status_code == 409
    assert "error" in resp.get_json()


def test_password_is_hashed_in_db(client):
    register(client)
    user = app_module.get_user_by_username("alice")
    assert user["password_hash"] != "secret123"


# ── Auth: login ──────────────────────────────────────────────────

def test_login_success(client):
    register(client)
    resp = login(client)
    assert resp.status_code == 200
    body = resp.get_json()
    assert isinstance(body["token"], str) and body["token"]


def test_login_wrong_password(client):
    register(client)
    resp = login(client, password="wrongpass")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_unknown_user(client):
    resp = login(client, username="ghost")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_missing_fields(client):
    resp = client.post("/auth/login", json={"username": "alice"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


# ── Auth protection on /tasks ────────────────────────────────────

def test_tasks_require_auth(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_tasks_reject_invalid_token(client):
    resp = client.get("/tasks", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_tasks_reject_malformed_header(client):
    resp = client.get("/tasks", headers={"Authorization": "not-bearer-format"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_create_task_requires_auth(client):
    resp = client.post("/tasks", json={"title": "Buy milk"})
    assert resp.status_code == 401


def test_get_task_requires_auth(client):
    resp = client.get("/tasks/1")
    assert resp.status_code == 401


def test_update_task_requires_auth(client):
    resp = client.put("/tasks/1", json={"status": "done"})
    assert resp.status_code == 401


# ── Task ownership / isolation ───────────────────────────────────

def test_user_sees_only_own_tasks(client):
    alice_headers = auth_header(client, "alice", "secret123")
    bob_headers = auth_header(client, "bob", "secret456")

    client.post("/tasks", json={"title": "Alice task"}, headers=alice_headers)
    client.post("/tasks", json={"title": "Bob task"}, headers=bob_headers)

    alice_tasks = client.get("/tasks", headers=alice_headers).get_json()["data"]
    bob_tasks = client.get("/tasks", headers=bob_headers).get_json()["data"]

    assert [t["title"] for t in alice_tasks] == ["Alice task"]
    assert [t["title"] for t in bob_tasks] == ["Bob task"]


def test_user_cannot_get_other_users_task(client):
    alice_headers = auth_header(client, "alice", "secret123")
    bob_headers = auth_header(client, "bob", "secret456")

    created = client.post("/tasks", json={"title": "Alice task"}, headers=alice_headers).get_json()

    resp = client.get(f"/tasks/{created['id']}", headers=bob_headers)
    assert resp.status_code == 404


def test_user_cannot_update_other_users_task(client):
    alice_headers = auth_header(client, "alice", "secret123")
    bob_headers = auth_header(client, "bob", "secret456")

    created = client.post("/tasks", json={"title": "Alice task"}, headers=alice_headers).get_json()

    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "done"}, headers=bob_headers
    )
    assert resp.status_code == 404

    # task must remain unchanged
    unchanged = client.get(f"/tasks/{created['id']}", headers=alice_headers).get_json()
    assert unchanged["status"] == "pending"


# ── Task CRUD (authenticated) ────────────────────────────────────

def test_create_task(client):
    headers = auth_header(client)
    resp = client.post("/tasks", json={"title": "Buy milk"}, headers=headers)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["title"] == "Buy milk"
    assert body["status"] == "pending"
    assert isinstance(body["id"], int)
    assert "created_at" in body


def test_create_task_missing_title(client):
    headers = auth_header(client)
    resp = client.post("/tasks", json={}, headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_empty_title(client):
    headers = auth_header(client)
    resp = client.post("/tasks", json={"title": "   "}, headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_no_body(client):
    headers = auth_header(client)
    resp = client.post("/tasks", headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_empty(client):
    headers = auth_header(client)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {"data": [], "next_cursor": None, "total": 0}


def test_list_tasks_ordered_desc(client):
    headers = auth_header(client)
    client.post("/tasks", json={"title": "first"}, headers=headers)
    client.post("/tasks", json={"title": "second"}, headers=headers)
    client.post("/tasks", json={"title": "third"}, headers=headers)

    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    titles = [t["title"] for t in body["data"]]
    assert titles == ["third", "second", "first"]
    assert body["next_cursor"] is None
    assert body["total"] == 3


def test_get_task(client):
    headers = auth_header(client)
    created = client.post("/tasks", json={"title": "Task A"}, headers=headers).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json() == created


def test_get_task_not_found(client):
    headers = auth_header(client)
    resp = client.get("/tasks/9999", headers=headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client):
    headers = auth_header(client)
    created = client.post("/tasks", json={"title": "Old title"}, headers=headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "New title"}, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "New title"
    assert body["status"] == "pending"


def test_update_task_status(client):
    headers = auth_header(client)
    created = client.post("/tasks", json={"title": "Task"}, headers=headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"}, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "done"
    assert body["title"] == "Task"


def test_update_task_title_and_status(client):
    headers = auth_header(client)
    created = client.post("/tasks", json={"title": "Task"}, headers=headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "Updated", "status": "done"}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "Updated"
    assert body["status"] == "done"


def test_update_task_invalid_status(client):
    headers = auth_header(client)
    created = client.post("/tasks", json={"title": "Task"}, headers=headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "archived"}, headers=headers)
    assert resp.status_code == 422
    assert "error" in resp.get_json()

    # task must remain unchanged
    unchanged = client.get(f"/tasks/{created['id']}", headers=headers).get_json()
    assert unchanged["status"] == "pending"


def test_update_task_not_found(client):
    headers = auth_header(client)
    resp = client.put("/tasks/9999", json={"title": "x"}, headers=headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_created_at_is_iso_string(client):
    headers = auth_header(client)
    created = client.post("/tasks", json={"title": "Task"}, headers=headers).get_json()
    assert isinstance(created["created_at"], str)
    from datetime import datetime

    datetime.fromisoformat(created["created_at"])


# ── Migration ──────────────────────────────────────────────────

def test_migration_adds_owner_id_to_existing_db(tmp_path):
    """Simulate a pre-auth database and verify init_db migrates it safely."""
    import sqlite3

    db_path = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE tasks ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  title TEXT NOT NULL,"
        "  status TEXT NOT NULL DEFAULT 'pending',"
        "  created_at TEXT NOT NULL"
        ")"
    )
    conn.execute(
        "INSERT INTO tasks (title, status, created_at) VALUES ('Legacy task', 'pending', '2020-01-01T00:00:00')"
    )
    conn.commit()
    conn.close()

    app_module.DATABASE = db_path
    app_module.init_db()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM tasks WHERE title = 'Legacy task'").fetchone()
    conn.close()

    assert row is not None
    assert row["owner_id"] is None
