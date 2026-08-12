"""
Tests for the Flask Task Management API (with JWT authentication).
"""

import json
import sqlite3
import time

import jwt
import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / "test_tasks.db"
    flask_app = create_app(database=str(db_path), jwt_secret="test-secret")
    flask_app.config.update(TESTING=True)
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, username="alice", password="s3cret-pw"):
    return client.post(
        "/auth/register",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


def login(client, username="alice", password="s3cret-pw"):
    return client.post(
        "/auth/login",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def token(client):
    """Register + login a default user, returning a valid JWT."""
    register(client, "alice", "s3cret-pw")
    resp = login(client, "alice", "s3cret-pw")
    return resp.get_json()["token"]


def create(client, token, title="Buy milk"):
    return client.post(
        "/tasks",
        data=json.dumps({"title": title}),
        content_type="application/json",
        headers=auth_headers(token),
    )


# ── POST /auth/register ─────────────────────────────────────

def test_register_success(client):
    resp = register(client, "bob", "password123")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["username"] == "bob"
    assert isinstance(body["id"], int)
    assert "password" not in body
    assert "password_hash" not in body


def test_register_missing_username_returns_400(client):
    resp = client.post(
        "/auth/register",
        data=json.dumps({"password": "password123"}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_missing_password_returns_400(client):
    resp = client.post(
        "/auth/register",
        data=json.dumps({"username": "bob"}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_duplicate_username_returns_409(client):
    register(client, "bob", "password123")
    resp = register(client, "bob", "another-pw")
    assert resp.status_code == 409
    assert "error" in resp.get_json()


def test_register_password_is_hashed_not_plaintext(client):
    register(client, "bob", "password123")
    app = client.application
    with app.app_context():
        from app import get_db

        row = get_db().execute(
            "SELECT password_hash FROM users WHERE username = ?", ("bob",)
        ).fetchone()
    assert row["password_hash"] != "password123"
    assert len(row["password_hash"]) > 20


# ── POST /auth/login ─────────────────────────────────────────

def test_login_success_returns_token(client):
    register(client, "bob", "password123")
    resp = login(client, "bob", "password123")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "token" in body
    assert isinstance(body["token"], str) and body["token"]


def test_login_wrong_password_returns_401(client):
    register(client, "bob", "password123")
    resp = login(client, "bob", "wrong-password")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_unknown_username_returns_401(client):
    resp = login(client, "ghost", "whatever")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_missing_fields_returns_400(client):
    resp = client.post(
        "/auth/login",
        data=json.dumps({"username": "bob"}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_token_contains_expected_claims(client):
    register(client, "bob", "password123")
    resp = login(client, "bob", "password123")
    token = resp.get_json()["token"]
    payload = jwt.decode(token, "test-secret", algorithms=["HS256"])
    assert payload["username"] == "bob"
    assert "user_id" in payload
    assert "exp" in payload


# ── Auth protection on /tasks/* ─────────────────────────────

def test_list_tasks_without_token_returns_401(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_create_task_without_token_returns_401(client):
    resp = client.post(
        "/tasks",
        data=json.dumps({"title": "No auth"}),
        content_type="application/json",
    )
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_get_task_without_token_returns_401(client, token):
    created = create(client, token, "Task").get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 401


def test_update_task_without_token_returns_401(client, token):
    created = create(client, token, "Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "done"}),
        content_type="application/json",
    )
    assert resp.status_code == 401


def test_malformed_authorization_header_returns_401(client):
    resp = client.get("/tasks", headers={"Authorization": "not-a-bearer-token"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_invalid_token_returns_401(client):
    resp = client.get("/tasks", headers=auth_headers("this.is.not-a-valid-jwt"))
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_token_signed_with_wrong_secret_returns_401(client, token):
    bad_token = jwt.encode(
        {"user_id": 1, "username": "alice"}, "wrong-secret", algorithm="HS256"
    )
    resp = client.get("/tasks", headers=auth_headers(bad_token))
    assert resp.status_code == 401


def test_expired_token_returns_401(client):
    import datetime

    register(client, "carl", "password123")
    expired = jwt.encode(
        {
            "user_id": 1,
            "username": "carl",
            "exp": datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(seconds=10),
        },
        "test-secret",
        algorithm="HS256",
    )
    resp = client.get("/tasks", headers=auth_headers(expired))
    assert resp.status_code == 401


# ── Per-user task isolation ──────────────────────────────────

def test_users_only_see_their_own_tasks(client):
    register(client, "alice", "pw-alice-1")
    register(client, "bob", "pw-bob-1")
    token_alice = login(client, "alice", "pw-alice-1").get_json()["token"]
    token_bob = login(client, "bob", "pw-bob-1").get_json()["token"]

    create(client, token_alice, "Alice task")
    create(client, token_bob, "Bob task")

    alice_tasks = client.get("/tasks", headers=auth_headers(token_alice)).get_json()
    bob_tasks = client.get("/tasks", headers=auth_headers(token_bob)).get_json()

    assert [t["title"] for t in alice_tasks["data"]] == ["Alice task"]
    assert [t["title"] for t in bob_tasks["data"]] == ["Bob task"]


def test_cannot_get_another_users_task(client):
    register(client, "alice", "pw-alice-1")
    register(client, "bob", "pw-bob-1")
    token_alice = login(client, "alice", "pw-alice-1").get_json()["token"]
    token_bob = login(client, "bob", "pw-bob-1").get_json()["token"]

    alice_task = create(client, token_alice, "Secret task").get_json()

    resp = client.get(f"/tasks/{alice_task['id']}", headers=auth_headers(token_bob))
    assert resp.status_code == 404


def test_cannot_update_another_users_task(client):
    register(client, "alice", "pw-alice-1")
    register(client, "bob", "pw-bob-1")
    token_alice = login(client, "alice", "pw-alice-1").get_json()["token"]
    token_bob = login(client, "bob", "pw-bob-1").get_json()["token"]

    alice_task = create(client, token_alice, "Secret task").get_json()

    resp = client.put(
        f"/tasks/{alice_task['id']}",
        data=json.dumps({"status": "done"}),
        content_type="application/json",
        headers=auth_headers(token_bob),
    )
    assert resp.status_code == 404

    # Task remains unaffected for the real owner.
    check = client.get(
        f"/tasks/{alice_task['id']}", headers=auth_headers(token_alice)
    ).get_json()
    assert check["status"] == "pending"


def test_created_task_has_owner_id(client, token):
    resp = create(client, token, "Owned task")
    body = resp.get_json()
    assert "owner_id" in body
    assert isinstance(body["owner_id"], int)


# ── POST /tasks ──────────────────────────────────────────────

def test_create_task_success(client, token):
    resp = create(client, token, "Write report")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["title"] == "Write report"
    assert body["status"] == "pending"
    assert isinstance(body["id"], int)
    assert "created_at" in body


def test_create_task_missing_title_returns_400(client, token):
    resp = client.post(
        "/tasks",
        data=json.dumps({}),
        content_type="application/json",
        headers=auth_headers(token),
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert "error" in body


def test_create_task_empty_title_returns_400(client, token):
    resp = create(client, token, "   ")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_no_body_returns_400(client, token):
    resp = client.post("/tasks", headers=auth_headers(token))
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_non_string_title_returns_400(client, token):
    resp = client.post(
        "/tasks",
        data=json.dumps({"title": 123}),
        content_type="application/json",
        headers=auth_headers(token),
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_strips_whitespace(client, token):
    resp = create(client, token, "  Padded title  ")
    assert resp.status_code == 201
    assert resp.get_json()["title"] == "Padded title"


# ── GET /tasks ───────────────────────────────────────────────

def test_list_tasks_empty(client, token):
    resp = client.get("/tasks", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {"data": [], "next_cursor": None, "total": 0}


def test_list_tasks_ordered_desc_by_created_at(client, token):
    create(client, token, "First")
    time.sleep(0.01)
    create(client, token, "Second")
    time.sleep(0.01)
    create(client, token, "Third")

    resp = client.get("/tasks", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.get_json()
    titles = [t["title"] for t in body["data"]]
    assert titles == ["Third", "Second", "First"]
    assert body["total"] == 3
    assert body["next_cursor"] is None


def test_list_tasks_returns_all_fields(client, token):
    create(client, token, "Task A")
    resp = client.get("/tasks", headers=auth_headers(token))
    task = resp.get_json()["data"][0]
    assert set(task.keys()) == {"id", "title", "status", "created_at", "owner_id"}


# ── GET /tasks/{id} ──────────────────────────────────────────

def test_get_single_task_success(client, token):
    created = create(client, token, "Detail task").get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["id"] == created["id"]
    assert body["title"] == "Detail task"


def test_get_single_task_not_found(client, token):
    resp = client.get("/tasks/9999", headers=auth_headers(token))
    assert resp.status_code == 404
    assert "error" in resp.get_json()


# ── PUT /tasks/{id} ──────────────────────────────────────────

def test_update_task_title(client, token):
    created = create(client, token, "Old title").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"title": "New title"}),
        content_type="application/json",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "New title"
    assert body["status"] == "pending"


def test_update_task_status(client, token):
    created = create(client, token, "Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "done"}),
        content_type="application/json",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "done"
    assert body["title"] == "Task"


def test_update_task_title_and_status(client, token):
    created = create(client, token, "Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"title": "Updated", "status": "in_progress"}),
        content_type="application/json",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "Updated"
    assert body["status"] == "in_progress"


def test_update_task_not_found(client, token):
    resp = client.put(
        "/tasks/9999",
        data=json.dumps({"title": "Nope"}),
        content_type="application/json",
        headers=auth_headers(token),
    )
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_no_fields_returns_400(client, token):
    created = create(client, token, "Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({}),
        content_type="application/json",
        headers=auth_headers(token),
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_update_task_empty_title_returns_400(client, token):
    created = create(client, token, "Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"title": "   "}),
        content_type="application/json",
        headers=auth_headers(token),
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_update_task_persists(client, token):
    created = create(client, token, "Task").get_json()
    client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "done"}),
        content_type="application/json",
        headers=auth_headers(token),
    )
    resp = client.get(f"/tasks/{created['id']}", headers=auth_headers(token))
    assert resp.get_json()["status"] == "done"


# ── Migration: pre-existing databases without auth ──────────

def test_schema_initialized_on_startup(tmp_path):
    db_path = tmp_path / "fresh.db"
    assert not db_path.exists()
    app = create_app(database=str(db_path))
    assert db_path.exists()

    client = app.test_client()
    register(client, "alice", "s3cret-pw")
    token = login(client, "alice", "s3cret-pw").get_json()["token"]
    resp = client.get("/tasks", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.get_json() == {"data": [], "next_cursor": None, "total": 0}


def test_migration_adds_owner_id_without_losing_existing_data(tmp_path):
    """Simulate a database created by the pre-auth version of the app."""
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_path))
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
    conn.close()

    # Booting the app must migrate the schema without raising and without
    # deleting the pre-existing row.
    app = create_app(database=str(db_path))

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
    assert "owner_id" in columns

    rows = conn.execute("SELECT * FROM tasks").fetchall()
    assert len(rows) == 1
    assert rows[0]["title"] == "Legacy task"
    assert rows[0]["owner_id"] is None
    conn.close()

    # A users table now exists too, so new registrations work against the
    # migrated database.
    client = app.test_client()
    resp = register(client, "alice", "s3cret-pw")
    assert resp.status_code == 201


# ── Misc ─────────────────────────────────────────────────────

def test_404_for_unknown_route(client):
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404
    body = resp.get_json()
    assert "error" in body
