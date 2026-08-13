import os
import time
from unittest.mock import patch

import pytest
import redis

import app as app_module


@pytest.fixture(autouse=True)
def _reset_rate_limit_storage():
    """Rate limit counters live in Redis, outside the per-test sqlite db, so
    they must be cleared between tests to keep tests independent."""
    store = redis.Redis.from_url(app_module.RATELIMIT_STORAGE_URI)
    store.flushdb()
    yield
    store.flushdb()


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
    titles = [t["title"] for t in resp.get_json()["data"]]
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
    body = resp.get_json()
    assert body == {"data": [], "next_cursor": None, "total": 0}


def test_list_tasks_ordered_desc_by_created_at(client):
    headers = _auth_headers(client)
    _create(client, "first", headers=headers)
    time.sleep(0.01)
    _create(client, "second", headers=headers)
    time.sleep(0.01)
    _create(client, "third", headers=headers)

    resp = client.get("/tasks", headers=headers)
    body = resp.get_json()
    titles = [t["title"] for t in body["data"]]
    assert titles == ["third", "second", "first"]
    assert body["next_cursor"] is None
    assert body["total"] == 3


def test_list_tasks_only_shows_own_tasks(client):
    alice_headers = _auth_headers(client, "alice", "pw1")
    bob_headers = _auth_headers(client, "bob", "pw2")

    _create(client, "alice task", headers=alice_headers)
    _create(client, "bob task", headers=bob_headers)

    alice_titles = [
        t["title"] for t in client.get("/tasks", headers=alice_headers).get_json()["data"]
    ]
    bob_titles = [
        t["title"] for t in client.get("/tasks", headers=bob_headers).get_json()["data"]
    ]

    assert alice_titles == ["alice task"]
    assert bob_titles == ["bob task"]


# ── GET /tasks pagination ─────────────────────────────────────


def test_list_tasks_default_limit_is_20(client):
    headers = _auth_headers(client)
    for i in range(25):
        _create(client, f"task {i}", headers=headers)

    resp = client.get("/tasks", headers=headers)
    body = resp.get_json()
    assert len(body["data"]) == 20
    assert body["total"] == 25
    assert body["next_cursor"] == body["data"][-1]["id"]


def test_list_tasks_second_page_via_cursor(client):
    headers = _auth_headers(client)
    for i in range(25):
        _create(client, f"task {i}", headers=headers)

    first_page = client.get("/tasks", headers=headers).get_json()
    second_page = client.get(
        f"/tasks?cursor={first_page['next_cursor']}", headers=headers
    ).get_json()

    assert len(second_page["data"]) == 5
    assert second_page["next_cursor"] is None
    assert second_page["total"] == 25

    first_ids = {t["id"] for t in first_page["data"]}
    second_ids = {t["id"] for t in second_page["data"]}
    assert first_ids.isdisjoint(second_ids)


def test_list_tasks_custom_limit(client):
    headers = _auth_headers(client)
    for i in range(5):
        _create(client, f"task {i}", headers=headers)

    resp = client.get("/tasks?limit=2", headers=headers)
    body = resp.get_json()
    assert len(body["data"]) == 2
    assert body["next_cursor"] == body["data"][-1]["id"]
    assert body["total"] == 5


def test_list_tasks_limit_capped_at_100(client):
    headers = _auth_headers(client)
    for i in range(3):
        _create(client, f"task {i}", headers=headers)

    resp = client.get("/tasks?limit=1000", headers=headers)
    body = resp.get_json()
    assert len(body["data"]) == 3
    assert body["next_cursor"] is None


def test_list_tasks_invalid_cursor_returns_400(client):
    headers = _auth_headers(client)
    resp = client.get("/tasks?cursor=not-an-int", headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_invalid_limit_returns_400(client):
    headers = _auth_headers(client)
    resp = client.get("/tasks?limit=not-an-int", headers=headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_cursor_from_other_users_task_returns_empty(client):
    alice_headers = _auth_headers(client, "alice", "pw1")
    bob_headers = _auth_headers(client, "bob", "pw2")
    alice_task = _create(client, "alice task", headers=alice_headers).get_json()

    resp = client.get(f"/tasks?cursor={alice_task['id']}", headers=bob_headers)
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["data"] == []


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


# ── Completion notification ──────────────────────────────────


def test_completing_task_triggers_notification(client):
    headers = _auth_headers(client, "alice", "pw1")
    created = _create(client, "ship feature", headers=headers).get_json()

    with patch.object(app_module.send_notification_email, "delay") as mock_delay:
        resp = client.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
        )

    assert resp.status_code == 200
    mock_delay.assert_called_once_with("alice@example.com", "ship feature")


def test_completing_already_completed_task_does_not_retrigger(client):
    headers = _auth_headers(client, "alice", "pw1")
    created = _create(client, "ship feature", headers=headers).get_json()
    client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers)

    with patch.object(app_module.send_notification_email, "delay") as mock_delay:
        client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers)

    mock_delay.assert_not_called()


def test_non_completed_status_change_does_not_trigger_notification(client):
    headers = _auth_headers(client)
    created = _create(client, "keep working", headers=headers).get_json()

    with patch.object(app_module.send_notification_email, "delay") as mock_delay:
        client.put(
            f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=headers
        )

    mock_delay.assert_not_called()


def test_updating_title_only_does_not_trigger_notification(client):
    headers = _auth_headers(client)
    created = _create(client, "keep working", headers=headers).get_json()

    with patch.object(app_module.send_notification_email, "delay") as mock_delay:
        client.put(f"/tasks/{created['id']}", json={"title": "renamed"}, headers=headers)

    mock_delay.assert_not_called()


def test_completing_nonexistent_task_does_not_trigger_notification(client):
    headers = _auth_headers(client)

    with patch.object(app_module.send_notification_email, "delay") as mock_delay:
        resp = client.put(
            "/tasks/9999", json={"status": "completed"}, headers=headers
        )

    assert resp.status_code == 404
    mock_delay.assert_not_called()


def test_completing_other_users_task_does_not_trigger_notification(client):
    alice_headers = _auth_headers(client, "alice", "pw1")
    bob_headers = _auth_headers(client, "bob", "pw2")
    created = _create(client, "alice's task", headers=alice_headers).get_json()

    with patch.object(app_module.send_notification_email, "delay") as mock_delay:
        client.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=bob_headers
        )

    mock_delay.assert_not_called()


def test_register_with_custom_email_used_for_notification(client):
    client.post(
        "/auth/register",
        json={"username": "carol", "password": "pw123", "email": "carol@work.com"},
    )
    token = _login(client, "carol", "pw123").get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    created = _create(client, "custom email task", headers=headers).get_json()

    with patch.object(app_module.send_notification_email, "delay") as mock_delay:
        client.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
        )

    mock_delay.assert_called_once_with("carol@work.com", "custom email task")


def test_send_notification_email_task_runs_without_broker(capsys):
    from notifications import send_notification_email

    send_notification_email("bob@example.com", "Write report")

    captured = capsys.readouterr()
    assert "bob@example.com" in captured.out
    assert "Write report" in captured.out


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


# ── Rate limiting ─────────────────────────────────────────────

RATE_LIMIT_COUNT = int(app_module.RATE_LIMIT.split(" ")[0])


def test_requests_within_limit_all_succeed(client):
    headers = _auth_headers(client)
    for _ in range(RATE_LIMIT_COUNT):
        resp = client.get("/tasks", headers=headers)
        assert resp.status_code == 200


def test_exceeding_limit_returns_429_with_retry_after(client):
    headers = _auth_headers(client)
    for _ in range(RATE_LIMIT_COUNT):
        client.get("/tasks", headers=headers)

    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 429
    assert "error" in resp.get_json()
    assert "Retry-After" in resp.headers
    assert int(resp.headers["Retry-After"]) >= 0


def test_rate_limit_is_scoped_per_user(client):
    alice_headers = _auth_headers(client, "alice", "pw1")
    bob_headers = _auth_headers(client, "bob", "pw2")

    for _ in range(RATE_LIMIT_COUNT):
        client.get("/tasks", headers=alice_headers)
    alice_resp = client.get("/tasks", headers=alice_headers)
    bob_resp = client.get("/tasks", headers=bob_headers)

    assert alice_resp.status_code == 429
    assert bob_resp.status_code == 200


def test_rate_limit_applies_to_auth_endpoints(client):
    for _ in range(RATE_LIMIT_COUNT):
        resp = client.post(
            "/auth/login", json={"username": "nobody", "password": "wrong"}
        )
        assert resp.status_code == 401

    resp = client.post("/auth/login", json={"username": "nobody", "password": "wrong"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_rate_limit_exempt_endpoints_do_not_share_bucket_with_auth(client):
    """Login attempts (keyed by IP) and task requests (keyed by user) draw from
    separate buckets, so exhausting one must not lock out the other."""
    headers = _auth_headers(client)
    for _ in range(RATE_LIMIT_COUNT):
        client.post("/auth/login", json={"username": "nobody", "password": "wrong"})

    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
