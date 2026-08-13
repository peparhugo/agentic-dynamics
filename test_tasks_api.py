import os
import sqlite3
import time

import pytest

from tasks_api import create_app, init_db


@pytest.fixture
def client(tmp_path):
    db_path = os.path.join(tmp_path, "test_tasks.db")
    app = create_app(db_path=db_path, secret_key="test-secret-key")
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def register(client, username="alice", password="password123"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="password123"):
    return client.post("/auth/login", json={"username": username, "password": password})


def make_auth_client(client, username="alice", password="password123"):
    """Register + log in a user and return the token to use as a Bearer header."""
    register(client, username, password)
    resp = login(client, username, password)
    return resp.get_json()["token"]


@pytest.fixture
def auth_client(client):
    """A test client pre-authenticated as a single default user."""
    token = make_auth_client(client)
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client


def create_task(client, title):
    return client.post("/tasks", json={"title": title})


# ── Task endpoints (now authenticated) ─────────────────────────────


def test_create_task_success(auth_client):
    resp = create_task(auth_client, "Buy milk")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["id"] == 1
    assert body["title"] == "Buy milk"
    assert body["status"] == "pending"
    assert "created_at" in body
    assert "owner_id" in body


def test_create_task_missing_title(auth_client):
    resp = auth_client.post("/tasks", json={})
    assert resp.status_code == 400
    body = resp.get_json()
    assert "error" in body


def test_create_task_blank_title(auth_client):
    resp = auth_client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400


def test_create_task_no_body(auth_client):
    resp = auth_client.post("/tasks")
    assert resp.status_code == 400


def test_ids_increment_manually(auth_client):
    r1 = create_task(auth_client, "Task 1").get_json()
    r2 = create_task(auth_client, "Task 2").get_json()
    r3 = create_task(auth_client, "Task 3").get_json()
    assert [r1["id"], r2["id"], r3["id"]] == [1, 2, 3]


def test_list_tasks_empty(auth_client):
    resp = auth_client.get("/tasks")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_tasks_ordered_desc(auth_client):
    create_task(auth_client, "First")
    time.sleep(0.01)
    create_task(auth_client, "Second")
    time.sleep(0.01)
    create_task(auth_client, "Third")

    resp = auth_client.get("/tasks")
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["Third", "Second", "First"]


def test_get_task_success(auth_client):
    created = create_task(auth_client, "Read book").get_json()
    resp = auth_client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Read book"


def test_get_task_not_found(auth_client):
    resp = auth_client.get("/tasks/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(auth_client):
    created = create_task(auth_client, "Old title").get_json()
    resp = auth_client.put(f"/tasks/{created['id']}", json={"title": "New title"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "New title"
    assert body["status"] == "pending"


def test_update_task_status(auth_client):
    created = create_task(auth_client, "Task").get_json()
    resp = auth_client.put(f"/tasks/{created['id']}", json={"status": "done"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "done"
    assert body["title"] == "Task"


def test_update_task_title_and_status(auth_client):
    created = create_task(auth_client, "Task").get_json()
    resp = auth_client.put(
        f"/tasks/{created['id']}", json={"title": "Updated", "status": "in_progress"}
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "Updated"
    assert body["status"] == "in_progress"


def test_update_task_not_found(auth_client):
    resp = auth_client.put("/tasks/999", json={"title": "Nope"})
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_no_fields(auth_client):
    created = create_task(auth_client, "Task").get_json()
    resp = auth_client.put(f"/tasks/{created['id']}", json={})
    assert resp.status_code == 400


def test_update_task_blank_title(auth_client):
    created = create_task(auth_client, "Task").get_json()
    resp = auth_client.put(f"/tasks/{created['id']}", json={"title": "  "})
    assert resp.status_code == 400


def test_full_response_is_json(auth_client):
    resp = create_task(auth_client, "JSON check")
    assert resp.content_type == "application/json"
    resp = auth_client.get("/tasks/999")
    assert resp.content_type == "application/json"


# ── Auth: registration ──────────────────────────────────────────────


def test_register_success(client):
    resp = register(client, "bob", "hunter22")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["username"] == "bob"
    assert "id" in body
    assert "password" not in body
    assert "password_hash" not in body


def test_register_duplicate_username(client):
    register(client, "bob", "hunter22")
    resp = register(client, "bob", "differentpass")
    assert resp.status_code == 409
    assert "error" in resp.get_json()


def test_register_missing_username(client):
    resp = client.post("/auth/register", json={"password": "hunter22"})
    assert resp.status_code == 400


def test_register_missing_password(client):
    resp = client.post("/auth/register", json={"username": "bob"})
    assert resp.status_code == 400


def test_register_short_password(client):
    resp = client.post("/auth/register", json={"username": "bob", "password": "123"})
    assert resp.status_code == 400


def test_register_blank_username(client):
    resp = client.post("/auth/register", json={"username": "   ", "password": "hunter22"})
    assert resp.status_code == 400


def test_password_is_hashed_in_db(client, tmp_path):
    db_path = os.path.join(tmp_path, "test_tasks.db")
    # The fixture already created the DB at a different path; create our own
    # app/db pairing so we can inspect the stored row directly.
    app = create_app(db_path=db_path, secret_key="test-secret-key")
    with app.test_client() as c:
        c.post("/auth/register", json={"username": "carol", "password": "supersecret"})

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE username = 'carol'").fetchone()
    conn.close()
    assert row["password_hash"] != "supersecret"
    assert row["password_hash"].startswith("pbkdf2:") or row["password_hash"].startswith("scrypt:")


# ── Auth: login ──────────────────────────────────────────────────────


def test_login_success(client):
    register(client, "bob", "hunter22")
    resp = login(client, "bob", "hunter22")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "token" in body
    assert isinstance(body["token"], str)


def test_login_wrong_password(client):
    register(client, "bob", "hunter22")
    resp = login(client, "bob", "wrongpassword")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_unknown_user(client):
    resp = login(client, "ghost", "whatever1")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_missing_fields(client):
    resp = client.post("/auth/login", json={"username": "bob"})
    assert resp.status_code == 400


# ── Task endpoints require auth ─────────────────────────────────────


def test_tasks_require_auth_no_header(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_create_task_requires_auth(client):
    resp = client.post("/tasks", json={"title": "Nope"})
    assert resp.status_code == 401


def test_get_task_requires_auth(client):
    resp = client.get("/tasks/1")
    assert resp.status_code == 401


def test_update_task_requires_auth(client):
    resp = client.put("/tasks/1", json={"title": "Nope"})
    assert resp.status_code == 401


def test_tasks_reject_malformed_header(client):
    client.environ_base["HTTP_AUTHORIZATION"] = "NotBearer sometoken"
    resp = client.get("/tasks")
    assert resp.status_code == 401


def test_tasks_reject_invalid_token(client):
    client.environ_base["HTTP_AUTHORIZATION"] = "Bearer not-a-real-token"
    resp = client.get("/tasks")
    assert resp.status_code == 401


def test_tasks_reject_token_signed_with_wrong_secret(client):
    import jwt as pyjwt

    register(client, "bob", "hunter22")
    forged = pyjwt.encode({"sub": 1}, "wrong-secret", algorithm="HS256")
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {forged}"
    resp = client.get("/tasks")
    assert resp.status_code == 401


# ── Per-user task isolation ──────────────────────────────────────────


def test_user_sees_only_own_tasks(client):
    alice_token = make_auth_client(client, "alice", "password123")
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {alice_token}"
    create_task(client, "Alice task 1")
    create_task(client, "Alice task 2")

    bob_token = make_auth_client(client, "bob", "password123")
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {bob_token}"
    create_task(client, "Bob task 1")

    resp = client.get("/tasks")
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["Bob task 1"]

    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {alice_token}"
    resp = client.get("/tasks")
    titles = [t["title"] for t in resp.get_json()]
    assert sorted(titles) == ["Alice task 1", "Alice task 2"]


def test_cannot_get_other_users_task(client):
    alice_token = make_auth_client(client, "alice", "password123")
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {alice_token}"
    alice_task = create_task(client, "Alice private task").get_json()

    bob_token = make_auth_client(client, "bob", "password123")
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {bob_token}"
    resp = client.get(f"/tasks/{alice_task['id']}")
    assert resp.status_code == 404


def test_cannot_update_other_users_task(client):
    alice_token = make_auth_client(client, "alice", "password123")
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {alice_token}"
    alice_task = create_task(client, "Alice private task").get_json()

    bob_token = make_auth_client(client, "bob", "password123")
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {bob_token}"
    resp = client.put(f"/tasks/{alice_task['id']}", json={"status": "done"})
    assert resp.status_code == 404


# ── Migration: pre-existing databases keep their data ────────────────


def test_migration_adds_owner_id_without_losing_data(tmp_path):
    db_path = os.path.join(tmp_path, "legacy.db")

    # Simulate a database created by the pre-auth version of the app: tasks
    # table with no owner_id column, no users table.
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE TABLE counters (name TEXT PRIMARY KEY, value INTEGER NOT NULL)"
    )
    conn.execute("INSERT INTO counters (name, value) VALUES ('task_id', 2)")
    conn.execute(
        "INSERT INTO tasks (id, title, status, created_at) VALUES (1, 'Legacy task', 'pending', '2024-01-01T00:00:00+00:00')"
    )
    conn.commit()
    conn.close()

    # Running init_db (as create_app does on startup) should migrate in place.
    init_db(db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
    assert "owner_id" in columns

    row = conn.execute("SELECT * FROM tasks WHERE id = 1").fetchone()
    assert row["title"] == "Legacy task"
    assert row["owner_id"] is None

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "users" in tables
    conn.close()

    # The app should still start cleanly against the migrated database.
    app = create_app(db_path=db_path, secret_key="test-secret-key")
    with app.test_client() as c:
        token = make_auth_client(c, "newowner", "password123")
        c.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        resp = c.get("/tasks")
        assert resp.status_code == 200
        # Legacy task has no owner, so the new user doesn't see it, but it's
        # still present in the database untouched.
        assert resp.get_json() == []
