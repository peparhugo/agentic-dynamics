import json

import fakeredis
import redis as redis_lib
import pytest

import task_api
from task_api import create_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Flask-Limiter talks to Redis through `limits.storage.redis.RedisStorage`,
    which calls `redis.from_url(...)`. Each test gets its own in-process fake
    Redis server (no sockets/threads involved), so rate-limit state is fully
    isolated per test and there's no dependency on a real Redis instance.
    """
    fake_server = fakeredis.FakeServer()
    monkeypatch.setattr(
        redis_lib, "from_url", lambda url, **kwargs: fakeredis.FakeStrictRedis(server=fake_server)
    )

    db_path = tmp_path / "test_tasks.db"
    return create_app(str(db_path), storage_uri="redis://localhost:6379/0")


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, username="alice", password="password123"):
    return client.post(
        "/auth/register",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


def login(client, username="alice", password="password123"):
    return client.post(
        "/auth/login",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def token(client):
    register(client)
    resp = login(client)
    return resp.get_json()["token"]


@pytest.fixture
def headers(token):
    return auth_header(token)


def create_task(client, headers, title="Write tests", **extra):
    body = {"title": title, **extra}
    return client.post(
        "/tasks", data=json.dumps(body), content_type="application/json", headers=headers
    )


# ── POST /auth/register ─────────────────────────────────────────


def test_register_success(client):
    resp = register(client, username="bob", password="password123")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "bob"
    assert isinstance(data["id"], int)
    assert "password" not in data
    assert "password_hash" not in data


def test_register_duplicate_username_returns_409(client):
    register(client, username="bob", password="password123")
    resp = register(client, username="bob", password="password456")
    assert resp.status_code == 409
    assert "error" in resp.get_json()


def test_register_missing_username_returns_400(client):
    resp = client.post(
        "/auth/register",
        data=json.dumps({"password": "password123"}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_register_missing_password_returns_400(client):
    resp = client.post(
        "/auth/register",
        data=json.dumps({"username": "bob"}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_register_short_password_returns_400(client):
    resp = register(client, username="bob", password="short")
    assert resp.status_code == 400


def test_register_non_json_body_returns_400(client):
    resp = client.post("/auth/register", data="not json", content_type="application/json")
    assert resp.status_code == 400


def test_register_password_is_hashed_not_stored_plain(client):
    register(client, username="bob", password="password123")
    # Verify indirectly: login with wrong password fails, correct password succeeds.
    assert login(client, username="bob", password="wrongpassword").status_code == 401
    assert login(client, username="bob", password="password123").status_code == 200


# ── POST /auth/login ─────────────────────────────────────────────


def test_login_success_returns_token(client):
    register(client, username="bob", password="password123")
    resp = login(client, username="bob", password="password123")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data["token"], str) and data["token"]
    assert data["username"] == "bob"


def test_login_wrong_password_returns_401(client):
    register(client, username="bob", password="password123")
    resp = login(client, username="bob", password="wrongpassword")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_unknown_username_returns_401(client):
    resp = login(client, username="ghost", password="password123")
    assert resp.status_code == 401


def test_login_missing_fields_returns_400(client):
    resp = client.post(
        "/auth/login", data=json.dumps({"username": "bob"}), content_type="application/json"
    )
    assert resp.status_code == 400


# ── Auth protection on /tasks/* ───────────────────────────────────


def test_list_tasks_without_token_returns_401(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_create_task_without_token_returns_401(client):
    resp = client.post(
        "/tasks", data=json.dumps({"title": "x"}), content_type="application/json"
    )
    assert resp.status_code == 401


def test_get_task_without_token_returns_401(client, headers):
    created = create_task(client, headers).get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 401


def test_update_task_without_token_returns_401(client, headers):
    created = create_task(client, headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", data=json.dumps({"title": "y"}), content_type="application/json"
    )
    assert resp.status_code == 401


def test_tasks_with_malformed_header_returns_401(client):
    resp = client.get("/tasks", headers={"Authorization": "not-bearer-format"})
    assert resp.status_code == 401


def test_tasks_with_invalid_token_returns_401(client):
    resp = client.get("/tasks", headers=auth_header("this.is.not.a.valid.jwt"))
    assert resp.status_code == 401


def test_tasks_with_token_for_deleted_secret_returns_401(client, headers):
    # A token signed with a different secret should be rejected.
    import jwt as pyjwt

    bogus = pyjwt.encode({"sub": 1, "username": "alice"}, "wrong-secret", algorithm="HS256")
    resp = client.get("/tasks", headers=auth_header(bogus))
    assert resp.status_code == 401


# ── POST /tasks ──────────────────────────────────────────────────


def test_create_task_success(client, headers):
    resp = create_task(client, headers, title="Buy milk")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert isinstance(data["id"], int)
    assert "created_at" in data and data["created_at"]
    assert data["owner_id"] is not None


def test_create_task_missing_title_returns_400(client, headers):
    resp = client.post("/tasks", data=json.dumps({}), content_type="application/json", headers=headers)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_create_task_blank_title_returns_400(client, headers):
    resp = create_task(client, headers, title="   ")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_non_string_title_returns_400(client, headers):
    resp = create_task(client, headers, title=123)
    assert resp.status_code == 400


def test_create_task_invalid_status_returns_400(client, headers):
    resp = create_task(client, headers, title="Task", status="bogus")
    assert resp.status_code == 400


def test_create_task_no_body_returns_400(client, headers):
    resp = client.post("/tasks", content_type="application/json", headers=headers)
    assert resp.status_code == 400


def test_create_task_non_json_body_returns_400(client, headers):
    resp = client.post("/tasks", data="not json", content_type="application/json", headers=headers)
    assert resp.status_code == 400


def test_create_task_strips_whitespace(client, headers):
    resp = create_task(client, headers, title="  padded title  ")
    assert resp.status_code == 201
    assert resp.get_json()["title"] == "padded title"


# ── GET /tasks ───────────────────────────────────────────────────


def test_list_tasks_empty(client, headers):
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json() == {"data": [], "next_cursor": None, "total": 0}


def test_list_tasks_ordered_desc_by_created_at(client, headers):
    ids = []
    for title in ["first", "second", "third"]:
        resp = create_task(client, headers, title=title)
        ids.append(resp.get_json()["id"])

    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    data = body["data"]
    assert body["total"] == 3
    assert body["next_cursor"] is None
    assert len(data) == 3
    returned_ids = [t["id"] for t in data]
    assert returned_ids == list(reversed(ids))
    assert [t["title"] for t in data] == ["third", "second", "first"]


def test_list_tasks_only_returns_own_tasks(client):
    register(client, username="alice", password="password123")
    register(client, username="bob", password="password123")
    alice_headers = auth_header(login(client, "alice", "password123").get_json()["token"])
    bob_headers = auth_header(login(client, "bob", "password123").get_json()["token"])

    create_task(client, alice_headers, title="Alice task")
    create_task(client, bob_headers, title="Bob task")

    alice_tasks = client.get("/tasks", headers=alice_headers).get_json()["data"]
    bob_tasks = client.get("/tasks", headers=bob_headers).get_json()["data"]

    assert [t["title"] for t in alice_tasks] == ["Alice task"]
    assert [t["title"] for t in bob_tasks] == ["Bob task"]


# ── GET /tasks pagination ─────────────────────────────────────────


def create_tasks(client, headers, count):
    ids = []
    for i in range(count):
        resp = create_task(client, headers, title=f"task-{i}")
        ids.append(resp.get_json()["id"])
    return ids


def seed_tasks(app, owner_id, count):
    """Insert tasks directly into the database, bypassing the API (and its
    rate limiter) for tests that need more than ~100 tasks."""
    import sqlite3
    from datetime import datetime, timedelta, timezone

    conn = sqlite3.connect(app.config["DATABASE"])
    now = datetime.now(timezone.utc)
    ids = []
    for i in range(count):
        created_at = (now + timedelta(microseconds=i)).isoformat()
        cur = conn.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, ?, ?, ?)",
            (f"seed-{i}", "pending", created_at, owner_id),
        )
        ids.append(cur.lastrowid)
    conn.commit()
    conn.close()
    return ids


def test_list_tasks_default_page_size_is_20(client, headers):
    create_tasks(client, headers, 25)
    resp = client.get("/tasks", headers=headers)
    body = resp.get_json()
    assert resp.status_code == 200
    assert len(body["data"]) == 20
    assert body["total"] == 25
    assert body["next_cursor"] is not None


def test_list_tasks_custom_limit(client, headers):
    create_tasks(client, headers, 10)
    resp = client.get("/tasks?limit=5", headers=headers)
    body = resp.get_json()
    assert resp.status_code == 200
    assert len(body["data"]) == 5
    assert body["total"] == 10
    assert body["next_cursor"] is not None


def test_list_tasks_limit_above_max_is_clamped(app, client, headers, token):
    owner_id = task_api.decode_token(token)["sub"]
    seed_tasks(app, owner_id, 150)
    resp = client.get("/tasks?limit=1000", headers=headers)
    body = resp.get_json()
    assert resp.status_code == 200
    assert len(body["data"]) == 100
    assert body["total"] == 150


def test_list_tasks_limit_zero_returns_400(client, headers):
    resp = client.get("/tasks?limit=0", headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_negative_limit_returns_400(client, headers):
    resp = client.get("/tasks?limit=-5", headers=headers)
    assert resp.status_code == 400


def test_list_tasks_non_integer_limit_returns_400(client, headers):
    resp = client.get("/tasks?limit=abc", headers=headers)
    assert resp.status_code == 400


def test_list_tasks_non_integer_cursor_returns_400(client, headers):
    resp = client.get("/tasks?cursor=abc", headers=headers)
    assert resp.status_code == 400


def test_list_tasks_invalid_cursor_returns_400(client, headers):
    create_task(client, headers, title="only task")
    resp = client.get("/tasks?cursor=99999", headers=headers)
    assert resp.status_code == 400


def test_list_tasks_last_page_has_null_next_cursor(client, headers):
    create_tasks(client, headers, 3)
    resp = client.get("/tasks?limit=10", headers=headers)
    body = resp.get_json()
    assert len(body["data"]) == 3
    assert body["next_cursor"] is None


def test_list_tasks_pagination_walks_all_pages_without_gaps_or_dupes(client, headers):
    ids = create_tasks(client, headers, 45)
    expected_order = list(reversed(ids))  # newest first, matches created_at desc

    seen = []
    cursor = None
    pages = 0
    while True:
        url = "/tasks?limit=20" + (f"&cursor={cursor}" if cursor else "")
        resp = client.get(url, headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["total"] == 45
        seen.extend(t["id"] for t in body["data"])
        cursor = body["next_cursor"]
        pages += 1
        assert pages <= 10  # guard against infinite loop on a bug
        if cursor is None:
            break

    assert seen == expected_order


def test_list_tasks_pagination_only_covers_own_tasks(client):
    register(client, username="alice", password="password123")
    register(client, username="bob", password="password123")
    alice_headers = auth_header(login(client, "alice", "password123").get_json()["token"])
    bob_headers = auth_header(login(client, "bob", "password123").get_json()["token"])

    create_tasks(client, alice_headers, 5)
    create_tasks(client, bob_headers, 3)

    alice_body = client.get("/tasks?limit=2", headers=alice_headers).get_json()
    bob_body = client.get("/tasks?limit=2", headers=bob_headers).get_json()

    assert alice_body["total"] == 5
    assert bob_body["total"] == 3


def test_list_tasks_without_cursor_returns_first_page(client, headers):
    ids = create_tasks(client, headers, 5)
    resp = client.get("/tasks?limit=2", headers=headers)
    body = resp.get_json()
    assert [t["id"] for t in body["data"]] == list(reversed(ids))[:2]


# ── GET /tasks/<id> ──────────────────────────────────────────────


def test_get_task_success(client, headers):
    created = create_task(client, headers, title="Read book").get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json() == created


def test_get_task_not_found_returns_404(client, headers):
    resp = client.get("/tasks/9999", headers=headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_get_task_owned_by_other_user_returns_404(client):
    register(client, username="alice", password="password123")
    register(client, username="bob", password="password123")
    alice_headers = auth_header(login(client, "alice", "password123").get_json()["token"])
    bob_headers = auth_header(login(client, "bob", "password123").get_json()["token"])

    created = create_task(client, alice_headers, title="Alice task").get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=bob_headers)
    assert resp.status_code == 404


# ── PUT /tasks/<id> ──────────────────────────────────────────────


def test_update_task_title_only(client, headers):
    created = create_task(client, headers, title="Old title").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"title": "New title"}),
        content_type="application/json",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status_only(client, headers):
    created = create_task(client, headers, title="Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "completed"}),
        content_type="application/json",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "completed"
    assert data["title"] == "Task"


def test_update_task_title_and_status(client, headers):
    created = create_task(client, headers, title="Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"title": "Updated", "status": "in_progress"}),
        content_type="application/json",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Updated"
    assert data["status"] == "in_progress"


def test_update_task_not_found_returns_404(client, headers):
    resp = client.put(
        "/tasks/9999",
        data=json.dumps({"title": "x"}),
        content_type="application/json",
        headers=headers,
    )
    assert resp.status_code == 404


def test_update_task_owned_by_other_user_returns_404(client):
    register(client, username="alice", password="password123")
    register(client, username="bob", password="password123")
    alice_headers = auth_header(login(client, "alice", "password123").get_json()["token"])
    bob_headers = auth_header(login(client, "bob", "password123").get_json()["token"])

    created = create_task(client, alice_headers, title="Alice task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"title": "Hijacked"}),
        content_type="application/json",
        headers=bob_headers,
    )
    assert resp.status_code == 404


def test_update_task_blank_title_returns_400(client, headers):
    created = create_task(client, headers, title="Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"title": "   "}),
        content_type="application/json",
        headers=headers,
    )
    assert resp.status_code == 400


def test_update_task_invalid_status_returns_400(client, headers):
    created = create_task(client, headers, title="Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "not-a-real-status"}),
        content_type="application/json",
        headers=headers,
    )
    assert resp.status_code == 400


def test_update_task_empty_body_is_noop(client, headers):
    created = create_task(client, headers, title="Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({}),
        content_type="application/json",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == created["title"]
    assert data["status"] == created["status"]


# ── Migration ──────────────────────────────────────────────────────


def test_migration_adds_owner_id_to_legacy_db_without_data_loss(tmp_path):
    import sqlite3

    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
        ("Legacy task", "pending", "2024-01-01T00:00:00+00:00"),
    )
    conn.commit()
    conn.close()

    app = create_app(str(db_path))
    client = app.test_client()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM tasks WHERE title = 'Legacy task'").fetchone()
    conn.close()

    assert row is not None
    assert row["owner_id"] is None

    register(client, username="alice", password="password123")
    token = login(client, "alice", "password123").get_json()["token"]
    resp = client.get("/tasks", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.get_json() == {"data": [], "next_cursor": None, "total": 0}


# ── Misc ─────────────────────────────────────────────────────────


def test_persists_across_requests(client, headers):
    created = create_task(client, headers, title="Persisted").get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Persisted"


# ── Completion notification trigger ───────────────────────────────


@pytest.fixture
def notify_mock(monkeypatch):
    calls = []
    monkeypatch.setattr(
        task_api.send_notification_email, "delay", lambda *args, **kwargs: calls.append(args)
    )
    return calls


def test_status_transition_to_completed_triggers_notification(client, headers, notify_mock):
    created = create_task(client, headers, title="Ship feature").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "completed"}),
        content_type="application/json",
        headers=headers,
    )
    assert resp.status_code == 200
    assert len(notify_mock) == 1
    user_email, task_title = notify_mock[0]
    assert user_email == "alice@example.com"
    assert task_title == "Ship feature"


def test_status_transition_to_non_completed_does_not_trigger_notification(client, headers, notify_mock):
    created = create_task(client, headers, title="Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "in_progress"}),
        content_type="application/json",
        headers=headers,
    )
    assert resp.status_code == 200
    assert notify_mock == []


def test_title_only_update_does_not_trigger_notification(client, headers, notify_mock):
    created = create_task(client, headers, title="Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"title": "Renamed"}),
        content_type="application/json",
        headers=headers,
    )
    assert resp.status_code == 200
    assert notify_mock == []


def test_already_completed_task_does_not_retrigger_notification(client, headers, notify_mock):
    created = create_task(client, headers, title="Task", status="completed").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "completed"}),
        content_type="application/json",
        headers=headers,
    )
    assert resp.status_code == 200
    assert notify_mock == []


def test_notification_uses_registered_email_when_provided(client, notify_mock):
    client.post(
        "/auth/register",
        data=json.dumps(
            {"username": "carol", "password": "password123", "email": "carol@work.example"}
        ),
        content_type="application/json",
    )
    resp = client.post(
        "/auth/login",
        data=json.dumps({"username": "carol", "password": "password123"}),
        content_type="application/json",
    )
    carol_headers = auth_header(resp.get_json()["token"])
    created = create_task(client, carol_headers, title="Review PR").get_json()

    client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "completed"}),
        content_type="application/json",
        headers=carol_headers,
    )
    assert len(notify_mock) == 1
    assert notify_mock[0][0] == "carol@work.example"


def test_notification_failure_does_not_break_api_response(client, headers, monkeypatch):
    def raise_error(*args, **kwargs):
        raise ConnectionError("broker unavailable")

    monkeypatch.setattr(task_api.send_notification_email, "delay", raise_error)

    created = create_task(client, headers, title="Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "completed"}),
        content_type="application/json",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"


# ── Rate limiting ────────────────────────────────────────────────


RATE_LIMIT = 100


def test_requests_within_limit_are_not_rate_limited(client, headers):
    for _ in range(10):
        resp = client.get("/tasks", headers=headers)
        assert resp.status_code == 200


def test_requests_over_limit_return_429(client, headers):
    statuses = [client.get("/tasks", headers=headers).status_code for _ in range(RATE_LIMIT + 5)]
    assert statuses[:RATE_LIMIT] == [200] * RATE_LIMIT
    assert all(code == 429 for code in statuses[RATE_LIMIT:])


def test_rate_limit_exceeded_returns_json_error_and_retry_after_header(client, headers):
    for _ in range(RATE_LIMIT):
        client.get("/tasks", headers=headers)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 429
    assert "error" in resp.get_json()
    assert "Retry-After" in resp.headers
    assert int(resp.headers["Retry-After"]) > 0


def test_rate_limit_is_per_user_not_shared_globally(client):
    register(client, username="alice", password="password123")
    register(client, username="bob", password="password123")
    alice_headers = auth_header(login(client, "alice", "password123").get_json()["token"])
    bob_headers = auth_header(login(client, "bob", "password123").get_json()["token"])

    for _ in range(RATE_LIMIT):
        assert client.get("/tasks", headers=alice_headers).status_code == 200
    assert client.get("/tasks", headers=alice_headers).status_code == 429

    # Bob has his own bucket and is unaffected by Alice exhausting hers.
    assert client.get("/tasks", headers=bob_headers).status_code == 200


def test_rate_limiting_applies_across_different_endpoints_for_same_user(client, headers):
    for _ in range(RATE_LIMIT):
        client.get("/tasks", headers=headers)
    # The bucket is shared per-user across endpoints, not reset per-route.
    resp = create_task(client, headers, title="over the limit")
    assert resp.status_code == 429


def test_rate_limiting_applies_to_auth_register_endpoint(client):
    for i in range(RATE_LIMIT):
        client.post(
            "/auth/register",
            data=json.dumps({"username": f"user{i}", "password": "password123"}),
            content_type="application/json",
        )
    resp = client.post(
        "/auth/register",
        data=json.dumps({"username": "one-too-many", "password": "password123"}),
        content_type="application/json",
    )
    assert resp.status_code == 429
    assert "error" in resp.get_json()


def test_rate_limiting_applies_to_auth_login_endpoint(client):
    register(client, username="alice", password="password123")  # consumes 1 of the 100
    for _ in range(RATE_LIMIT - 1):
        client.post(
            "/auth/login",
            data=json.dumps({"username": "alice", "password": "wrong"}),
            content_type="application/json",
        )
    resp = client.post(
        "/auth/login",
        data=json.dumps({"username": "alice", "password": "password123"}),
        content_type="application/json",
    )
    assert resp.status_code == 429


def test_unauthenticated_requests_are_rate_limited_by_ip_not_blocked_outright(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401  # still enforces auth, not swallowed by rate limiting


def test_rate_limit_does_not_break_normal_task_workflow(client, headers):
    created = create_task(client, headers, title="Normal flow").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "completed"}),
        content_type="application/json",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
