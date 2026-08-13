import os
import sqlite3
import tempfile
from unittest.mock import patch

import pytest

from tasks_app import create_app


@pytest.fixture
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    app = create_app(database=path)
    app.testing = True
    with app.test_client() as client:
        yield client
    os.remove(path)


@pytest.fixture
def make_client():
    """Like `client`, but lets a test pick a custom rate limit."""
    created = []

    def _make(rate_limit="100 per minute"):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        app = create_app(database=path, rate_limit=rate_limit)
        app.testing = True
        test_client = app.test_client()
        created.append((test_client, path))
        return test_client

    yield _make

    for test_client, path in created:
        os.remove(path)


def register(client, username="alice", password="hunter2pass"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="hunter2pass"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_headers(client, username="alice", password="hunter2pass"):
    register(client, username, password)
    token = login(client, username, password).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def create_task(client, title="Buy milk", headers=None):
    if headers is None:
        headers = auth_headers(client)
    return client.post("/tasks", json={"title": title}, headers=headers)


# ── Auth: register ──────────────────────────────────────────────


def test_register_success(client):
    resp = register(client)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "alice"
    assert isinstance(data["id"], int)
    assert "password" not in data
    assert "password_hash" not in data


def test_register_missing_username_returns_400(client):
    resp = client.post("/auth/register", json={"password": "hunter2pass"})
    assert resp.status_code == 400


def test_register_missing_password_returns_400(client):
    resp = client.post("/auth/register", json={"username": "alice"})
    assert resp.status_code == 400


def test_register_duplicate_username_returns_409(client):
    register(client, "alice", "hunter2pass")
    resp = register(client, "alice", "otherpass123")
    assert resp.status_code == 409


# ── Auth: login ─────────────────────────────────────────────────


def test_login_success(client):
    register(client, "alice", "hunter2pass")
    resp = login(client, "alice", "hunter2pass")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data and isinstance(data["token"], str)


def test_login_wrong_password_returns_401(client):
    register(client, "alice", "hunter2pass")
    resp = login(client, "alice", "wrongpassword")
    assert resp.status_code == 401


def test_login_unknown_user_returns_401(client):
    resp = login(client, "ghost", "hunter2pass")
    assert resp.status_code == 401


# ── Auth: protection of /tasks ──────────────────────────────────


def test_tasks_requires_auth_missing_header_returns_401(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_tasks_requires_auth_invalid_token_returns_401(client):
    resp = client.get("/tasks", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_tasks_requires_auth_malformed_header_returns_401(client):
    resp = client.get("/tasks", headers={"Authorization": "not-bearer-token"})
    assert resp.status_code == 401


def test_create_task_without_auth_returns_401(client):
    resp = client.post("/tasks", json={"title": "Buy milk"})
    assert resp.status_code == 401


# ── Per-user task isolation ──────────────────────────────────────


def test_users_only_see_their_own_tasks(client):
    alice_headers = auth_headers(client, "alice", "hunter2pass")
    bob_headers = auth_headers(client, "bob", "swordfish123")

    create_task(client, "Alice task", headers=alice_headers)
    create_task(client, "Bob task", headers=bob_headers)

    alice_tasks = client.get("/tasks", headers=alice_headers).get_json()["data"]
    bob_tasks = client.get("/tasks", headers=bob_headers).get_json()["data"]

    assert [t["title"] for t in alice_tasks] == ["Alice task"]
    assert [t["title"] for t in bob_tasks] == ["Bob task"]


def test_get_other_users_task_returns_404(client):
    alice_headers = auth_headers(client, "alice", "hunter2pass")
    bob_headers = auth_headers(client, "bob", "swordfish123")

    created = create_task(client, "Alice task", headers=alice_headers).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=bob_headers)
    assert resp.status_code == 404


def test_update_other_users_task_returns_404(client):
    alice_headers = auth_headers(client, "alice", "hunter2pass")
    bob_headers = auth_headers(client, "bob", "swordfish123")

    created = create_task(client, "Alice task", headers=alice_headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "Hacked"}, headers=bob_headers
    )
    assert resp.status_code == 404


# ── Existing task behavior (now authenticated) ───────────────────


def test_create_task_success(client):
    headers = auth_headers(client)
    resp = create_task(client, "Write tests", headers=headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Write tests"
    assert data["status"] == "pending"
    assert isinstance(data["id"], int)
    assert "created_at" in data


def test_create_task_missing_title_returns_400(client):
    headers = auth_headers(client)
    resp = client.post("/tasks", json={}, headers=headers)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_create_task_blank_title_returns_400(client):
    headers = auth_headers(client)
    resp = client.post("/tasks", json={"title": "   "}, headers=headers)
    assert resp.status_code == 400


def test_create_task_no_body_returns_400(client):
    headers = auth_headers(client)
    resp = client.post("/tasks", headers=headers)
    assert resp.status_code == 400


def test_list_tasks_empty(client):
    headers = auth_headers(client)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {"data": [], "next_cursor": None, "total": 0}


def test_list_tasks_ordered_desc_by_created_at(client):
    headers = auth_headers(client)
    create_task(client, "First", headers=headers)
    create_task(client, "Second", headers=headers)
    create_task(client, "Third", headers=headers)

    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    titles = [t["title"] for t in body["data"]]
    assert titles == ["Third", "Second", "First"]
    assert body["total"] == 3
    assert body["next_cursor"] is None


def test_get_task_success(client):
    headers = auth_headers(client)
    created = create_task(client, "Read book", headers=headers).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == created["id"]
    assert data["title"] == "Read book"


def test_get_task_not_found(client):
    headers = auth_headers(client)
    resp = client.get("/tasks/999", headers=headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client):
    headers = auth_headers(client)
    created = create_task(client, "Old title", headers=headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "New title"}, headers=headers
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status(client):
    headers = auth_headers(client)
    created = create_task(client, "Task", headers=headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "done"}, headers=headers
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "done"
    assert data["title"] == "Task"


def test_update_task_title_and_status(client):
    headers = auth_headers(client)
    created = create_task(client, "Task", headers=headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "Updated", "status": "in_progress"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Updated"
    assert data["status"] == "in_progress"


def test_update_task_not_found(client):
    headers = auth_headers(client)
    resp = client.put("/tasks/999", json={"title": "x"}, headers=headers)
    assert resp.status_code == 404


def test_update_task_empty_body_returns_400(client):
    headers = auth_headers(client)
    created = create_task(client, "Task", headers=headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={}, headers=headers)
    assert resp.status_code == 400


def test_update_task_blank_title_returns_400(client):
    headers = auth_headers(client)
    created = create_task(client, "Task", headers=headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "   "}, headers=headers)
    assert resp.status_code == 400


# ── Completion notification trigger ───────────────────────────────


def test_update_task_to_completed_triggers_notification(client):
    headers = auth_headers(client)
    created = create_task(client, "Ship report", headers=headers).get_json()

    with patch("tasks_app.send_notification_email") as mock_task:
        resp = client.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
        )
        assert resp.status_code == 200
        mock_task.delay.assert_called_once_with("alice", "Ship report")


def test_update_task_to_non_completed_status_does_not_trigger_notification(client):
    headers = auth_headers(client)
    created = create_task(client, "Task", headers=headers).get_json()

    with patch("tasks_app.send_notification_email") as mock_task:
        resp = client.put(
            f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=headers
        )
        assert resp.status_code == 200
        mock_task.delay.assert_not_called()


def test_update_task_title_only_does_not_trigger_notification(client):
    headers = auth_headers(client)
    created = create_task(client, "Task", headers=headers).get_json()

    with patch("tasks_app.send_notification_email") as mock_task:
        resp = client.put(
            f"/tasks/{created['id']}", json={"title": "Renamed"}, headers=headers
        )
        assert resp.status_code == 200
        mock_task.delay.assert_not_called()


def test_update_task_already_completed_does_not_retrigger_notification(client):
    headers = auth_headers(client)
    created = create_task(client, "Task", headers=headers).get_json()

    with patch("tasks_app.send_notification_email") as mock_task:
        client.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
        )
        mock_task.delay.reset_mock()

        resp = client.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
        )
        assert resp.status_code == 200
        mock_task.delay.assert_not_called()


def test_update_task_completed_uses_owner_username_as_notification_recipient(client):
    alice_headers = auth_headers(client, "alice", "hunter2pass")
    created = create_task(client, "Alice task", headers=alice_headers).get_json()

    with patch("tasks_app.send_notification_email") as mock_task:
        client.put(
            f"/tasks/{created['id']}",
            json={"status": "completed"},
            headers=alice_headers,
        )
        mock_task.delay.assert_called_once_with("alice", "Alice task")


def test_notification_broker_failure_does_not_break_response(client):
    headers = auth_headers(client)
    created = create_task(client, "Task", headers=headers).get_json()

    with patch("tasks_app.send_notification_email") as mock_task:
        mock_task.delay.side_effect = ConnectionError("broker unavailable")
        resp = client.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "completed"


# ── Migration: pre-auth databases keep their data ────────────────


def test_migration_adds_owner_id_without_dropping_existing_rows():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        legacy = sqlite3.connect(path)
        legacy.execute(
            """
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
            """
        )
        legacy.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
            ("legacy task", "pending", "2020-01-01T00:00:00"),
        )
        legacy.commit()
        legacy.close()

        app = create_app(database=path)
        app.testing = True

        columns = {
            row[1]
            for row in sqlite3.connect(path).execute("PRAGMA table_info(tasks)")
        }
        assert "owner_id" in columns

        row = sqlite3.connect(path).execute(
            "SELECT title, owner_id FROM tasks WHERE title = 'legacy task'"
        ).fetchone()
        assert row == ("legacy task", None)
    finally:
        os.remove(path)


# ── Pagination ────────────────────────────────────────────────────


def _create_tasks(client, headers, count):
    for i in range(count):
        create_task(client, f"Task {i}", headers=headers)


def test_list_tasks_default_page_size_is_20(client):
    headers = auth_headers(client)
    _create_tasks(client, headers, 25)

    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["data"]) == 20
    assert body["total"] == 25
    assert body["next_cursor"] == str(body["data"][-1]["id"])


def test_list_tasks_pagination_walks_every_item_exactly_once(client):
    headers = auth_headers(client)
    _create_tasks(client, headers, 25)

    seen_ids = []
    cursor = None
    for _ in range(10):
        params = {"limit": "10"}
        if cursor is not None:
            params["cursor"] = cursor
        resp = client.get("/tasks", query_string=params, headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()
        seen_ids.extend(t["id"] for t in body["data"])
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert len(seen_ids) == 25
    assert len(set(seen_ids)) == 25


def test_list_tasks_custom_limit_is_respected(client):
    headers = auth_headers(client)
    _create_tasks(client, headers, 5)

    resp = client.get("/tasks", query_string={"limit": "2"}, headers=headers)
    body = resp.get_json()
    assert len(body["data"]) == 2
    assert body["next_cursor"] is not None


def test_list_tasks_limit_is_capped_at_100(client):
    headers = auth_headers(client)
    _create_tasks(client, headers, 5)

    resp = client.get("/tasks", query_string={"limit": "1000"}, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["data"]) == 5
    assert body["next_cursor"] is None


def test_list_tasks_last_page_has_null_next_cursor(client):
    headers = auth_headers(client)
    _create_tasks(client, headers, 3)

    resp = client.get("/tasks", query_string={"limit": "10"}, headers=headers)
    body = resp.get_json()
    assert len(body["data"]) == 3
    assert body["next_cursor"] is None
    assert body["total"] == 3


def test_list_tasks_no_cursor_returns_first_page(client):
    headers = auth_headers(client)
    _create_tasks(client, headers, 3)

    resp = client.get("/tasks", headers=headers)
    body = resp.get_json()
    titles = [t["title"] for t in body["data"]]
    assert titles == ["Task 2", "Task 1", "Task 0"]


def test_list_tasks_invalid_cursor_returns_400(client):
    headers = auth_headers(client)
    resp = client.get(
        "/tasks", query_string={"cursor": "not-a-number"}, headers=headers
    )
    assert resp.status_code == 400


def test_list_tasks_invalid_limit_returns_400(client):
    headers = auth_headers(client)
    resp = client.get(
        "/tasks", query_string={"limit": "not-a-number"}, headers=headers
    )
    assert resp.status_code == 400


def test_list_tasks_non_positive_limit_returns_400(client):
    headers = auth_headers(client)
    resp = client.get("/tasks", query_string={"limit": "0"}, headers=headers)
    assert resp.status_code == 400


def test_list_tasks_pagination_isolated_per_user(client):
    alice_headers = auth_headers(client, "alice", "hunter2pass")
    bob_headers = auth_headers(client, "bob", "swordfish123")
    _create_tasks(client, alice_headers, 3)
    _create_tasks(client, bob_headers, 2)

    alice_body = client.get("/tasks", headers=alice_headers).get_json()
    bob_body = client.get("/tasks", headers=bob_headers).get_json()

    assert alice_body["total"] == 3
    assert bob_body["total"] == 2


# ── Rate limiting ────────────────────────────────────────────────


def test_requests_within_limit_all_succeed(make_client):
    client = make_client(rate_limit="5 per minute")
    headers = auth_headers(client)

    responses = [client.get("/tasks", headers=headers) for _ in range(5)]
    assert all(r.status_code == 200 for r in responses)


def test_request_over_limit_returns_429(make_client):
    client = make_client(rate_limit="3 per minute")
    headers = auth_headers(client)

    for _ in range(3):
        assert client.get("/tasks", headers=headers).status_code == 200

    blocked = client.get("/tasks", headers=headers)
    assert blocked.status_code == 429
    assert "error" in blocked.get_json()


def test_429_response_has_retry_after_header(make_client):
    # Registration and login are rate limited by IP (no user identity yet),
    # so the limit must cover those two calls before the user-keyed quota
    # for /tasks is exercised below.
    client = make_client(rate_limit="2 per minute")
    headers = auth_headers(client)

    client.get("/tasks", headers=headers)
    client.get("/tasks", headers=headers)
    blocked = client.get("/tasks", headers=headers)

    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert int(blocked.headers["Retry-After"]) >= 0


def test_rate_limit_applies_to_auth_endpoints(make_client):
    client = make_client(rate_limit="2 per minute")

    for _ in range(2):
        resp = client.post(
            "/auth/login", json={"username": "ghost", "password": "whatever1"}
        )
        assert resp.status_code == 401

    blocked = client.post(
        "/auth/login", json={"username": "ghost", "password": "whatever1"}
    )
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_rate_limit_is_per_user_not_shared(make_client):
    # Both users register/login from the same test-client IP (4 IP-keyed
    # requests total), so the limit must be high enough to cover that
    # before each user's independent /tasks quota is exercised below.
    client = make_client(rate_limit="5 per minute")
    alice_headers = auth_headers(client, "alice", "hunter2pass")
    bob_headers = auth_headers(client, "bob", "swordfish123")

    for _ in range(5):
        assert client.get("/tasks", headers=alice_headers).status_code == 200

    assert client.get("/tasks", headers=alice_headers).status_code == 429
    # Bob has his own quota and is unaffected by Alice exhausting hers.
    assert client.get("/tasks", headers=bob_headers).status_code == 200


def test_rate_limit_is_shared_across_endpoints_for_same_user(make_client):
    client = make_client(rate_limit="3 per minute")
    headers = auth_headers(client)

    assert client.get("/tasks", headers=headers).status_code == 200
    assert create_task(client, "Task", headers=headers).status_code == 201
    assert client.get("/tasks", headers=headers).status_code == 200

    blocked = client.get("/tasks", headers=headers)
    assert blocked.status_code == 429
