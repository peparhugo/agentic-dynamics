"""
Test suite for the Flask Task Management API (app.py).

Covers:
 - POST /auth/register (success + duplicate username -> 409 + missing fields -> 400)
 - POST /auth/login (success + wrong password/unknown user -> 401)
 - JWT protection on /tasks/* (missing/invalid/expired token -> 401)
 - Per-user task isolation (users only see their own tasks)
 - POST /tasks (success + missing title -> 400)
 - GET /tasks (list, ordered by created_at desc)
 - GET /tasks/{id} (found + 404 when missing)
 - PUT /tasks/{id} (update title and/or status + 404 when missing)
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import jwt
import pytest

# Make sure the project root (parent of tests/) is importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Provide a Flask test client backed by a fresh SQLite DB file per test."""
    db_path = tmp_path / "test_tasks.db"
    monkeypatch.setattr(app_module, "DATABASE", str(db_path))
    app_module.init_db()

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client


def _register(client, username="alice", password="s3cret-pw"):
    return client.post(
        "/auth/register",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


def _login(client, username="alice", password="s3cret-pw"):
    return client.post(
        "/auth/login",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def _register_and_login(client, username="alice", password="s3cret-pw"):
    _register(client, username, password)
    token = _login(client, username, password).get_json()["token"]
    return _auth_header(token)


def _create_task(client, headers, title="Buy milk"):
    return client.post(
        "/tasks",
        data=json.dumps({"title": title}),
        content_type="application/json",
        headers=headers,
    )


# ── POST /auth/register ───────────────────────────────────────────


def test_register_success(client):
    resp = _register(client, "alice", "s3cret-pw")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["username"] == "alice"
    assert isinstance(body["id"], int)
    assert "password" not in body
    assert "password_hash" not in body


def test_register_duplicate_username_returns_409(client):
    _register(client, "alice", "s3cret-pw")
    resp = _register(client, "alice", "different-pw")
    assert resp.status_code == 409
    assert "error" in resp.get_json()


def test_register_missing_username_returns_400(client):
    resp = client.post(
        "/auth/register",
        data=json.dumps({"password": "s3cret-pw"}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_missing_password_returns_400(client):
    resp = client.post(
        "/auth/register",
        data=json.dumps({"username": "alice"}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_password_is_hashed_not_stored_plaintext(client):
    _register(client, "alice", "s3cret-pw")
    user = app_module.get_user_by_username("alice")
    assert user["password_hash"] != "s3cret-pw"
    assert app_module.check_password_hash(user["password_hash"], "s3cret-pw")


# ── POST /auth/login ───────────────────────────────────────────────


def test_login_success_returns_token(client):
    _register(client, "alice", "s3cret-pw")
    resp = _login(client, "alice", "s3cret-pw")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "token" in body
    # Token should decode and reference the registered user.
    payload = jwt.decode(
        body["token"], app_module.SECRET_KEY, algorithms=[app_module.JWT_ALGORITHM]
    )
    user = app_module.get_user_by_username("alice")
    assert payload["sub"] == user["id"]


def test_login_wrong_password_returns_401(client):
    _register(client, "alice", "s3cret-pw")
    resp = _login(client, "alice", "wrong-pw")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_unknown_user_returns_401(client):
    resp = _login(client, "ghost", "whatever")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_missing_fields_returns_400(client):
    resp = client.post(
        "/auth/login",
        data=json.dumps({"username": "alice"}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


# ── JWT protection on /tasks/* ─────────────────────────────────────


def test_list_tasks_without_token_returns_401(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_create_task_without_token_returns_401(client):
    resp = client.post(
        "/tasks",
        data=json.dumps({"title": "Nope"}),
        content_type="application/json",
    )
    assert resp.status_code == 401


def test_tasks_with_malformed_header_returns_401(client):
    resp = client.get("/tasks", headers={"Authorization": "NotBearer sometoken"})
    assert resp.status_code == 401


def test_tasks_with_invalid_token_returns_401(client):
    resp = client.get("/tasks", headers=_auth_header("this.is.not.a.valid.jwt"))
    assert resp.status_code == 401


def test_tasks_with_expired_token_returns_401(client):
    headers = _register_and_login(client)
    user = app_module.get_user_by_username("alice")
    expired_payload = {
        "sub": user["id"],
        "iat": datetime.now(timezone.utc) - timedelta(minutes=120),
        "exp": datetime.now(timezone.utc) - timedelta(minutes=60),
    }
    expired_token = jwt.encode(
        expired_payload, app_module.SECRET_KEY, algorithm=app_module.JWT_ALGORITHM
    )
    resp = client.get("/tasks", headers=_auth_header(expired_token))
    assert resp.status_code == 401


def test_tasks_with_token_for_deleted_user_returns_401(client):
    headers = _register_and_login(client)
    token = headers["Authorization"].split()[1]
    with app_module.get_db() as conn:
        conn.execute("DELETE FROM users WHERE username = ?", ("alice",))
        conn.commit()
    resp = client.get("/tasks", headers=_auth_header(token))
    assert resp.status_code == 401


def test_valid_token_allows_access(client):
    headers = _register_and_login(client)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200


# ── Per-user task isolation ─────────────────────────────────────────


def test_users_only_see_their_own_tasks(client):
    alice_headers = _register_and_login(client, "alice", "pw-alice")
    bob_headers = _register_and_login(client, "bob", "pw-bob")

    _create_task(client, alice_headers, "Alice's task")
    _create_task(client, bob_headers, "Bob's task")

    alice_tasks = client.get("/tasks", headers=alice_headers).get_json()
    bob_tasks = client.get("/tasks", headers=bob_headers).get_json()

    assert [t["title"] for t in alice_tasks] == ["Alice's task"]
    assert [t["title"] for t in bob_tasks] == ["Bob's task"]


def test_user_cannot_get_other_users_task(client):
    alice_headers = _register_and_login(client, "alice", "pw-alice")
    bob_headers = _register_and_login(client, "bob", "pw-bob")

    created = _create_task(client, alice_headers, "Alice's task").get_json()

    resp = client.get(f"/tasks/{created['id']}", headers=bob_headers)
    assert resp.status_code == 404


def test_user_cannot_update_other_users_task(client):
    alice_headers = _register_and_login(client, "alice", "pw-alice")
    bob_headers = _register_and_login(client, "bob", "pw-bob")

    created = _create_task(client, alice_headers, "Alice's task").get_json()

    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "done"}),
        content_type="application/json",
        headers=bob_headers,
    )
    assert resp.status_code == 404

    # Confirm Alice's task was untouched.
    unchanged = client.get(f"/tasks/{created['id']}", headers=alice_headers).get_json()
    assert unchanged["status"] == "pending"


# ── POST /tasks ──────────────────────────────────────────────────


def test_create_task_success(client):
    headers = _register_and_login(client)
    resp = _create_task(client, headers, "Write report")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["title"] == "Write report"
    assert body["status"] == "pending"
    assert isinstance(body["id"], int)
    assert "created_at" in body
    assert body["owner_id"] == app_module.get_user_by_username("alice")["id"]


def test_create_task_missing_title_returns_400(client):
    headers = _register_and_login(client)
    resp = client.post(
        "/tasks", data=json.dumps({}), content_type="application/json", headers=headers
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert "error" in body


def test_create_task_blank_title_returns_400(client):
    headers = _register_and_login(client)
    resp = client.post(
        "/tasks",
        data=json.dumps({"title": "   "}),
        content_type="application/json",
        headers=headers,
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert "error" in body


def test_create_task_no_json_body_returns_400(client):
    headers = _register_and_login(client)
    resp = client.post("/tasks", headers=headers)
    assert resp.status_code == 400
    body = resp.get_json()
    assert "error" in body


# ── GET /tasks ───────────────────────────────────────────────────


def test_list_tasks_empty(client):
    headers = _register_and_login(client)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_tasks_ordered_by_created_at_desc(client):
    headers = _register_and_login(client)
    _create_task(client, headers, "First task")
    _create_task(client, headers, "Second task")
    _create_task(client, headers, "Third task")

    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["Third task", "Second task", "First task"]


# ── GET /tasks/{id} ──────────────────────────────────────────────


def test_get_single_task_success(client):
    headers = _register_and_login(client)
    created = _create_task(client, headers, "Read book").get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["id"] == created["id"]
    assert body["title"] == "Read book"


def test_get_single_task_not_found(client):
    headers = _register_and_login(client)
    resp = client.get("/tasks/9999", headers=headers)
    assert resp.status_code == 404
    body = resp.get_json()
    assert "error" in body


# ── PUT /tasks/{id} ──────────────────────────────────────────────


def test_update_task_title_only(client):
    headers = _register_and_login(client)
    created = _create_task(client, headers, "Old title").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"title": "New title"}),
        content_type="application/json",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "New title"
    assert body["status"] == "pending"


def test_update_task_status_only(client):
    headers = _register_and_login(client)
    created = _create_task(client, headers, "Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "done"}),
        content_type="application/json",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "Task"
    assert body["status"] == "done"


def test_update_task_title_and_status(client):
    headers = _register_and_login(client)
    created = _create_task(client, headers, "Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"title": "Updated", "status": "in_progress"}),
        content_type="application/json",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "Updated"
    assert body["status"] == "in_progress"


def test_update_task_not_found(client):
    headers = _register_and_login(client)
    resp = client.put(
        "/tasks/9999",
        data=json.dumps({"title": "Nope"}),
        content_type="application/json",
        headers=headers,
    )
    assert resp.status_code == 404
    body = resp.get_json()
    assert "error" in body


def test_update_task_persisted(client):
    headers = _register_and_login(client)
    created = _create_task(client, headers, "Persisted task").get_json()
    client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "done"}),
        content_type="application/json",
        headers=headers,
    )
    resp = client.get(f"/tasks/{created['id']}", headers=headers)
    assert resp.get_json()["status"] == "done"


# ── Migration ─────────────────────────────────────────────────────


def test_migration_adds_owner_id_to_legacy_tasks_table(tmp_path, monkeypatch):
    """Simulate a pre-auth database (no owner_id / users table) and verify
    init_db() migrates it in place without dropping existing rows."""
    db_path = tmp_path / "legacy.db"
    monkeypatch.setattr(app_module, "DATABASE", str(db_path))

    with app_module.get_db() as conn:
        conn.execute(
            "CREATE TABLE tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL"
            ")"
        )
        conn.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
            ("Legacy task", "pending", "2020-01-01T00:00:00"),
        )
        conn.commit()

    app_module.init_db()

    with app_module.get_db() as conn:
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(tasks)")]
        assert "owner_id" in columns
        rows = conn.execute("SELECT * FROM tasks").fetchall()
        assert len(rows) == 1
        assert rows[0]["title"] == "Legacy task"
        assert rows[0]["owner_id"] is None
