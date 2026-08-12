import sqlite3
import os
import pytest

os.environ["TASK_DATABASE"] = "test_tasks.db"

import task_api
from task_api import app, init_db

PASSWORD = "password123"


@pytest.fixture()
def client(tmp_path):
    task_api.DATABASE = str(tmp_path / "test_tasks.db")
    init_db()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def register(client, username="alice", password=PASSWORD):
    return client.post(
        "/auth/register", json={"username": username, "password": password}
    )


def login(client, username="alice", password=PASSWORD):
    resp = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200
    return resp.get_json()["token"]


def auth_headers(client, username="alice", password=PASSWORD):
    register(client, username, password)
    token = login(client, username, password)
    return {"Authorization": f"Bearer {token}"}


def create_task(client, title="Buy milk", headers=None):
    return client.post("/tasks", json={"title": title}, headers=headers)


# ── Auth endpoints ──────────────────────────────────────────────

def test_register_creates_user(client):
    resp = register(client)
    assert resp.status_code == 201
    assert resp.get_json()["username"] == "alice"


def test_register_duplicate_username(client):
    assert register(client).status_code == 201
    resp = register(client)
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "username already taken"


def test_register_missing_fields(client):
    resp = client.post("/auth/register", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "username and password are required"


def test_register_short_password(client):
    resp = client.post(
        "/auth/register", json={"username": "bob", "password": "short"}
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "password must be at least 8 characters"


def test_register_hashes_password(client):
    register(client)
    with task_api.get_db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username = 'alice'"
        ).fetchone()
    assert row["password_hash"] != PASSWORD


def test_login_returns_jwt(client):
    register(client)
    resp = client.post(
        "/auth/login", json={"username": "alice", "password": PASSWORD}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data
    assert data["username"] == "alice"


def test_login_wrong_password(client):
    register(client)
    resp = client.post(
        "/auth/login", json={"username": "alice", "password": "wrongpass1"}
    )
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "invalid credentials"


def test_login_unknown_user(client):
    resp = client.post(
        "/auth/login", json={"username": "nobody", "password": PASSWORD}
    )
    assert resp.status_code == 401


def test_login_missing_fields(client):
    resp = client.post("/auth/login", json={})
    assert resp.status_code == 400


# ── Protected endpoints: missing/invalid tokens ────────────────

def test_tasks_require_auth(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401


def test_create_task_requires_auth(client):
    resp = client.post("/tasks", json={"title": "Buy milk"})
    assert resp.status_code == 401


def test_get_task_requires_auth(client):
    resp = client.get("/tasks/1")
    assert resp.status_code == 401


def test_update_task_requires_auth(client):
    resp = client.put("/tasks/1", json={"title": "x"})
    assert resp.status_code == 401


def test_delete_task_requires_auth(client):
    resp = client.delete("/tasks/1")
    assert resp.status_code == 401


def test_invalid_token_rejected(client):
    resp = client.get("/tasks", headers={"Authorization": "Bearer not.a.token"})
    assert resp.status_code == 401


def test_malformed_header_rejected(client):
    resp = client.get("/tasks", headers={"Authorization": "Token abc"})
    assert resp.status_code == 401


# ── Protected endpoints: CRUD ──────────────────────────────────

def test_create_task(client):
    headers = auth_headers(client)
    resp = client.post("/tasks", json={"title": "Buy milk"}, headers=headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_create_task_missing_title(client):
    headers = auth_headers(client)
    resp = client.post("/tasks", json={}, headers=headers)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "title is required"


def test_create_task_blank_title(client):
    headers = auth_headers(client)
    resp = client.post("/tasks", json={"title": "   "}, headers=headers)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "title is required"


def test_list_tasks_ordered_by_created_at_desc(client):
    headers = auth_headers(client)
    client.post("/tasks", json={"title": "first"}, headers=headers)
    client.post("/tasks", json={"title": "second"}, headers=headers)
    client.post("/tasks", json={"title": "third"}, headers=headers)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 3
    titles = [t["title"] for t in data]
    assert titles == ["third", "second", "first"]


def test_get_task(client):
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Buy milk"}, headers=headers
    ).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Buy milk"


def test_get_task_not_found(client):
    headers = auth_headers(client)
    resp = client.get("/tasks/999", headers=headers)
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "task not found"


def test_update_task_title(client):
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Buy milk"}, headers=headers
    ).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "Buy oat milk"}, headers=headers
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Buy oat milk"
    assert data["status"] == "pending"


def test_update_task_status(client):
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Buy milk"}, headers=headers
    ).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"


def test_update_task_not_found(client):
    headers = auth_headers(client)
    resp = client.put("/tasks/999", json={"title": "x"}, headers=headers)
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "task not found"


def test_update_task_invalid_status(client):
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Buy milk"}, headers=headers
    ).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "nonsense"}, headers=headers
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid status"


def test_update_task_blank_title(client):
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Buy milk"}, headers=headers
    ).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "  "}, headers=headers
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "title is required"


def test_delete_task(client):
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Buy milk"}, headers=headers
    ).get_json()
    resp = client.delete(f"/tasks/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["message"] == "task deleted"
    assert client.get(f"/tasks/{created['id']}", headers=headers).status_code == 404


def test_json_error_message_shape(client):
    headers = auth_headers(client)
    resp = client.post("/tasks", json={"title": ""}, headers=headers)
    body = resp.get_json()
    assert resp.status_code == 400
    assert isinstance(body, dict)
    assert "error" in body


# ── Per-user isolation ──────────────────────────────────────────

def test_users_only_see_their_own_tasks(client):
    alice = auth_headers(client, username="alice")
    bob = auth_headers(client, username="bob")
    client.post("/tasks", json={"title": "alice task"}, headers=alice)
    client.post("/tasks", json={"title": "bob task"}, headers=bob)

    alice_tasks = client.get("/tasks", headers=alice).get_json()
    bob_tasks = client.get("/tasks", headers=bob).get_json()
    assert [t["title"] for t in alice_tasks] == ["alice task"]
    assert [t["title"] for t in bob_tasks] == ["bob task"]


def test_user_cannot_get_others_task(client):
    alice = auth_headers(client, username="alice")
    bob = auth_headers(client, username="bob")
    created = client.post(
        "/tasks", json={"title": "alice task"}, headers=alice
    ).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=bob)
    assert resp.status_code == 404


def test_user_cannot_update_others_task(client):
    alice = auth_headers(client, username="alice")
    bob = auth_headers(client, username="bob")
    created = client.post(
        "/tasks", json={"title": "alice task"}, headers=alice
    ).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "hacked"}, headers=bob
    )
    assert resp.status_code == 404


def test_user_cannot_delete_others_task(client):
    alice = auth_headers(client, username="alice")
    bob = auth_headers(client, username="bob")
    created = client.post(
        "/tasks", json={"title": "alice task"}, headers=alice
    ).get_json()
    resp = client.delete(f"/tasks/{created['id']}", headers=bob)
    assert resp.status_code == 404
    assert client.get(
        f"/tasks/{created['id']}", headers=alice
    ).status_code == 200


# ── Migration ───────────────────────────────────────────────────

def test_migrate_preserves_existing_tasks(tmp_path):
    db_path = str(tmp_path / "old.db")
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        );
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        INSERT INTO tasks (title, status, created_at)
        VALUES ('legacy task', 'pending', '2020-01-01T00:00:00');
    """)
    conn.commit()
    conn.close()

    task_api.DATABASE = db_path
    init_db()

    with task_api.get_db() as c:
        rows = c.execute("SELECT * FROM tasks").fetchall()
    assert len(rows) == 1
    assert rows[0]["title"] == "legacy task"
    assert rows[0]["owner_id"] is not None
    assert rows[0]["status"] == "pending"


def test_init_db_idempotent(tmp_path):
    task_api.DATABASE = str(tmp_path / "twice.db")
    init_db()
    init_db()
    with task_api.get_db() as conn:
        tasks = conn.execute("PRAGMA table_info(tasks)").fetchall()
    cols = {row[1] for row in tasks}
    assert "owner_id" in cols
