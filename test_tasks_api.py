import os
import sqlite3
import time
from unittest.mock import patch

import fakeredis
import pytest

from tasks_api import create_app, init_db


@pytest.fixture
def client(tmp_path):
    db_path = os.path.join(tmp_path, "test_tasks.db")
    # In-memory rate-limit storage keeps each test isolated from the others
    # (and from needing a real Redis server); the Redis backend itself is
    # exercised separately in the rate limiting tests below.
    app = create_app(db_path=db_path, secret_key="test-secret-key", storage_uri="memory://")
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
    assert resp.get_json() == {"data": [], "next_cursor": None, "total": 0}


def test_list_tasks_ordered_desc(auth_client):
    create_task(auth_client, "First")
    time.sleep(0.01)
    create_task(auth_client, "Second")
    time.sleep(0.01)
    create_task(auth_client, "Third")

    resp = auth_client.get("/tasks")
    assert resp.status_code == 200
    body = resp.get_json()
    titles = [t["title"] for t in body["data"]]
    assert titles == ["Third", "Second", "First"]
    assert body["next_cursor"] is None
    assert body["total"] == 3


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
    app = create_app(db_path=db_path, secret_key="test-secret-key", storage_uri="memory://")
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
    titles = [t["title"] for t in resp.get_json()["data"]]
    assert titles == ["Bob task 1"]

    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {alice_token}"
    resp = client.get("/tasks")
    titles = [t["title"] for t in resp.get_json()["data"]]
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
    app = create_app(db_path=db_path, secret_key="test-secret-key", storage_uri="memory://")
    with app.test_client() as c:
        token = make_auth_client(c, "newowner", "password123")
        c.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        resp = c.get("/tasks")
        assert resp.status_code == 200
        # Legacy task has no owner, so the new user doesn't see it, but it's
        # still present in the database untouched.
        assert resp.get_json() == {"data": [], "next_cursor": None, "total": 0}


# ── Registration: email ───────────────────────────────────────────────


def test_register_default_email(client):
    resp = register(client, "dana", "password123")
    assert resp.status_code == 201
    assert resp.get_json()["email"] == "dana@example.com"


def test_register_custom_email(client):
    resp = client.post(
        "/auth/register",
        json={"username": "erin", "password": "password123", "email": "erin@company.com"},
    )
    assert resp.status_code == 201
    assert resp.get_json()["email"] == "erin@company.com"


def test_register_blank_email_rejected(client):
    resp = client.post(
        "/auth/register",
        json={"username": "frank", "password": "password123", "email": "   "},
    )
    assert resp.status_code == 400


# ── Completion notification trigger ─────────────────────────────────────


def test_completing_task_triggers_notification_email(auth_client):
    created = create_task(auth_client, "Ship feature").get_json()
    with patch("tasks_api.send_notification_email.delay") as mock_delay:
        resp = auth_client.put(f"/tasks/{created['id']}", json={"status": "completed"})

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
    mock_delay.assert_called_once_with("alice@example.com", "Ship feature")


def test_completing_task_with_title_change_uses_new_title(auth_client):
    created = create_task(auth_client, "Old title").get_json()
    with patch("tasks_api.send_notification_email.delay") as mock_delay:
        resp = auth_client.put(
            f"/tasks/{created['id']}", json={"title": "New title", "status": "completed"}
        )

    assert resp.status_code == 200
    mock_delay.assert_called_once_with("alice@example.com", "New title")


def test_updating_to_non_completed_status_does_not_notify(auth_client):
    created = create_task(auth_client, "Task").get_json()
    with patch("tasks_api.send_notification_email.delay") as mock_delay:
        resp = auth_client.put(f"/tasks/{created['id']}", json={"status": "in_progress"})

    assert resp.status_code == 200
    mock_delay.assert_not_called()


def test_already_completed_task_does_not_renotify(auth_client):
    created = create_task(auth_client, "Task").get_json()
    auth_client.put(f"/tasks/{created['id']}", json={"status": "completed"})

    with patch("tasks_api.send_notification_email.delay") as mock_delay:
        resp = auth_client.put(f"/tasks/{created['id']}", json={"title": "Renamed"})

    assert resp.status_code == 200
    mock_delay.assert_not_called()


def test_title_only_update_does_not_notify(auth_client):
    created = create_task(auth_client, "Task").get_json()
    with patch("tasks_api.send_notification_email.delay") as mock_delay:
        resp = auth_client.put(f"/tasks/{created['id']}", json={"title": "Renamed"})

    assert resp.status_code == 200
    mock_delay.assert_not_called()


def test_notification_enqueue_failure_does_not_break_response(auth_client):
    created = create_task(auth_client, "Task").get_json()
    with patch("tasks_api.send_notification_email.delay", side_effect=Exception("broker down")):
        resp = auth_client.put(f"/tasks/{created['id']}", json={"status": "completed"})

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"


def test_completing_other_users_task_is_not_possible_and_does_not_notify(client):
    alice_token = make_auth_client(client, "alice", "password123")
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {alice_token}"
    alice_task = create_task(client, "Alice private task").get_json()

    bob_token = make_auth_client(client, "bob", "password123")
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {bob_token}"
    with patch("tasks_api.send_notification_email.delay") as mock_delay:
        resp = client.put(f"/tasks/{alice_task['id']}", json={"status": "completed"})

    assert resp.status_code == 404
    mock_delay.assert_not_called()


# ── Pagination ─────────────────────────────────────────────────────


def make_app(tmp_path, name="test_tasks.db", **kwargs):
    db_path = os.path.join(tmp_path, name)
    kwargs.setdefault("storage_uri", "memory://")
    return create_app(db_path=db_path, secret_key="test-secret-key", **kwargs)


def test_list_tasks_default_page_size(tmp_path):
    # 25 tasks need a bumped-up per-test rate limit; the default 100/minute
    # is fine in production but this test alone would eat most of it.
    app = make_app(tmp_path, rate_limit="1000 per minute")
    with app.test_client() as c:
        token = make_auth_client(c, "alice", "password123")
        c.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        for i in range(25):
            create_task(c, f"Task {i}")

        resp = c.get("/tasks")
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]) == 20
        assert body["total"] == 25
        assert body["next_cursor"] is not None
        # Newest first.
        assert body["data"][0]["title"] == "Task 24"


def test_list_tasks_pagination_follows_cursor(tmp_path):
    app = make_app(tmp_path, rate_limit="1000 per minute")
    with app.test_client() as c:
        token = make_auth_client(c, "alice", "password123")
        c.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        for i in range(25):
            create_task(c, f"Task {i}")

        page1 = c.get("/tasks").get_json()
        assert len(page1["data"]) == 20
        assert page1["next_cursor"] is not None

        page2 = c.get(f"/tasks?cursor={page1['next_cursor']}").get_json()
        assert len(page2["data"]) == 5
        assert page2["next_cursor"] is None
        assert page2["total"] == 25

        page1_ids = {t["id"] for t in page1["data"]}
        page2_ids = {t["id"] for t in page2["data"]}
        assert page1_ids.isdisjoint(page2_ids)
        assert len(page1_ids | page2_ids) == 25


def test_list_tasks_custom_limit(auth_client):
    for i in range(5):
        create_task(auth_client, f"Task {i}")

    resp = auth_client.get("/tasks?limit=2")
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["data"]) == 2
    assert body["total"] == 5
    assert body["next_cursor"] is not None


def test_list_tasks_limit_clamped_to_max(tmp_path):
    app = make_app(tmp_path, rate_limit="1000 per minute")
    with app.test_client() as c:
        token = make_auth_client(c, "alice", "password123")
        c.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        for i in range(105):
            create_task(c, f"Task {i}")

        resp = c.get("/tasks?limit=1000")
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]) == 100
        assert body["total"] == 105


def test_list_tasks_invalid_cursor(auth_client):
    resp = auth_client.get("/tasks?cursor=not-a-number")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_invalid_limit_not_a_number(auth_client):
    resp = auth_client.get("/tasks?limit=not-a-number")
    assert resp.status_code == 400


def test_list_tasks_invalid_limit_zero(auth_client):
    resp = auth_client.get("/tasks?limit=0")
    assert resp.status_code == 400


def test_list_tasks_invalid_limit_negative(auth_client):
    resp = auth_client.get("/tasks?limit=-1")
    assert resp.status_code == 400


def test_list_tasks_without_cursor_returns_first_page(auth_client):
    create_task(auth_client, "Only task")
    resp = auth_client.get("/tasks")
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["data"]) == 1
    assert body["next_cursor"] is None


# ── Rate limiting ─────────────────────────────────────────────────


def test_rate_limit_exceeded_returns_429_with_retry_after(tmp_path):
    app = make_app(tmp_path, rate_limit="3 per minute")
    with app.test_client() as c:
        token = make_auth_client(c, "alice", "password123")
        c.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        for _ in range(3):
            resp = c.get("/tasks")
            assert resp.status_code == 200

        resp = c.get("/tasks")
        assert resp.status_code == 429
        assert "error" in resp.get_json()
        assert "Retry-After" in resp.headers


def test_rate_limit_applies_to_auth_endpoints(tmp_path):
    app = make_app(tmp_path, rate_limit="2 per minute")
    with app.test_client() as c:
        resp = c.post("/auth/register", json={"username": "alice", "password": "password123"})
        assert resp.status_code == 201

        resp = c.post("/auth/login", json={"username": "alice", "password": "password123"})
        assert resp.status_code == 200

        resp = c.post("/auth/login", json={"username": "alice", "password": "wrong"})
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers


def test_rate_limit_is_isolated_per_authenticated_user(tmp_path):
    app = make_app(tmp_path, rate_limit="2 per minute")
    with app.test_client() as c:
        # Distinct source IPs keep registration/login (unauthenticated,
        # IP-keyed) from sharing a bucket with each other or with the
        # authenticated, user-keyed requests checked below.
        c.environ_base["REMOTE_ADDR"] = "10.0.0.1"
        alice_token = make_auth_client(c, "alice", "password123")

        c.environ_base["REMOTE_ADDR"] = "10.0.0.2"
        bob_token = make_auth_client(c, "bob", "password123")

        c.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {alice_token}"
        assert c.get("/tasks").status_code == 200
        assert c.get("/tasks").status_code == 200
        assert c.get("/tasks").status_code == 429

        c.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {bob_token}"
        resp = c.get("/tasks")
        assert resp.status_code == 200


def test_rate_limiting_uses_redis_storage_backend(tmp_path):
    """The production storage backend is Redis; verify that code path works
    end-to-end using fakeredis in place of a live Redis server."""
    fake_redis = fakeredis.FakeStrictRedis()
    with patch("redis.from_url", return_value=fake_redis):
        app = make_app(
            tmp_path, storage_uri="redis://localhost:6379/2", rate_limit="2 per minute"
        )
        with app.test_client() as c:
            token = make_auth_client(c, "alice", "password123")
            c.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"

            assert c.get("/tasks").status_code == 200
            assert c.get("/tasks").status_code == 200
            resp = c.get("/tasks")
            assert resp.status_code == 429
            assert "Retry-After" in resp.headers


def test_rate_limit_storage_defaults_to_redis(tmp_path):
    db_path = os.path.join(tmp_path, "test_tasks.db")
    with patch("redis.from_url", return_value=fakeredis.FakeStrictRedis()):
        app = create_app(db_path=db_path, secret_key="test-secret-key")
    assert app.config["RATELIMIT_STORAGE_URI"].startswith("redis://")
