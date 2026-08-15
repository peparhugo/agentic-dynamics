from unittest.mock import patch

import pytest

import app as app_module


@pytest.fixture
def client(tmp_path):
    app_module.DATABASE = str(tmp_path / "test.db")
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client):
    client.post("/auth/register", json={"username": "alice", "password": "hunter2"})
    resp = client.post("/auth/login", json={"username": "alice", "password": "hunter2"})
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def other_auth_headers(client):
    client.post("/auth/register", json={"username": "bob", "password": "hunter2"})
    resp = client.post("/auth/login", json={"username": "bob", "password": "hunter2"})
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ── Auth: registration ───────────────────────────────────────


def test_register_user(client):
    resp = client.post("/auth/register", json={"username": "alice", "password": "hunter2"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "alice"
    assert isinstance(data["id"], int)
    assert "password" not in data
    assert "password_hash" not in data


def test_register_missing_username(client):
    resp = client.post("/auth/register", json={"password": "hunter2"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_missing_password(client):
    resp = client.post("/auth/register", json={"username": "alice"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_duplicate_username(client):
    client.post("/auth/register", json={"username": "alice", "password": "hunter2"})
    resp = client.post("/auth/register", json={"username": "alice", "password": "other"})
    assert resp.status_code == 409
    assert "error" in resp.get_json()


# ── Auth: login ───────────────────────────────────────────────


def test_login_success(client):
    client.post("/auth/register", json={"username": "alice", "password": "hunter2"})
    resp = client.post("/auth/login", json={"username": "alice", "password": "hunter2"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data["token"], str) and data["token"]


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "alice", "password": "hunter2"})
    resp = client.post("/auth/login", json={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_login_unknown_user(client):
    resp = client.post("/auth/login", json={"username": "ghost", "password": "hunter2"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


# ── Auth: protection on /tasks ───────────────────────────────


def test_tasks_requires_auth(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_tasks_rejects_invalid_token(client):
    resp = client.get("/tasks", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_tasks_rejects_missing_bearer_prefix(client, auth_headers):
    token = auth_headers["Authorization"].split(" ", 1)[1]
    resp = client.get("/tasks", headers={"Authorization": token})
    assert resp.status_code == 401


def test_create_task_requires_auth(client):
    resp = client.post("/tasks", json={"title": "Buy milk"})
    assert resp.status_code == 401


def test_users_only_see_own_tasks(client, auth_headers):
    client.post("/tasks", json={"title": "alice task"}, headers=auth_headers)
    bob_headers = other_auth_headers(client)
    client.post("/tasks", json={"title": "bob task"}, headers=bob_headers)

    alice_tasks = client.get("/tasks", headers=auth_headers).get_json()["data"]
    bob_tasks = client.get("/tasks", headers=bob_headers).get_json()["data"]

    assert [t["title"] for t in alice_tasks] == ["alice task"]
    assert [t["title"] for t in bob_tasks] == ["bob task"]


def test_cannot_get_other_users_task(client, auth_headers):
    created = client.post("/tasks", json={"title": "alice task"}, headers=auth_headers).get_json()
    bob_headers = other_auth_headers(client)
    resp = client.get(f"/tasks/{created['id']}", headers=bob_headers)
    assert resp.status_code == 404


def test_cannot_update_other_users_task(client, auth_headers):
    created = client.post("/tasks", json={"title": "alice task"}, headers=auth_headers).get_json()
    bob_headers = other_auth_headers(client)
    resp = client.put(f"/tasks/{created['id']}", json={"title": "hijacked"}, headers=bob_headers)
    assert resp.status_code == 404


# ── Tasks: existing behavior (now under auth) ────────────────


def test_create_task(client, auth_headers):
    resp = client.post("/tasks", json={"title": "Buy milk"}, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert isinstance(data["id"], int)
    assert "created_at" in data


def test_create_task_missing_title(client, auth_headers):
    resp = client.post("/tasks", json={}, headers=auth_headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_blank_title(client, auth_headers):
    resp = client.post("/tasks", json={"title": "   "}, headers=auth_headers)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_no_body(client, auth_headers):
    resp = client.post("/tasks", headers=auth_headers)
    assert resp.status_code == 400


def test_list_tasks_empty(client, auth_headers):
    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json() == {"data": [], "next_cursor": None, "total": 0}


def test_list_tasks_ordered_desc(client, auth_headers):
    client.post("/tasks", json={"title": "first"}, headers=auth_headers)
    client.post("/tasks", json={"title": "second"}, headers=auth_headers)
    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    data = body["data"]
    assert len(data) == 2
    assert data[0]["title"] == "second"
    assert data[1]["title"] == "first"
    assert body["next_cursor"] is None
    assert body["total"] == 2


# ── Pagination ────────────────────────────────────────────────


def test_list_tasks_default_limit_and_no_cursor(client, auth_headers):
    for i in range(3):
        client.post("/tasks", json={"title": f"task {i}"}, headers=auth_headers)
    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["data"]) == 3
    assert body["total"] == 3
    assert body["next_cursor"] is None


def test_list_tasks_respects_limit_param(client, auth_headers):
    created = [
        client.post("/tasks", json={"title": f"task {i}"}, headers=auth_headers).get_json()
        for i in range(5)
    ]
    resp = client.get("/tasks?limit=2", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["data"]) == 2
    assert body["total"] == 5
    newest_first_ids = [t["id"] for t in reversed(created)]
    assert [t["id"] for t in body["data"]] == newest_first_ids[:2]
    assert body["next_cursor"] == newest_first_ids[1]


def test_list_tasks_cursor_walks_all_pages(client, auth_headers):
    created = [
        client.post("/tasks", json={"title": f"task {i}"}, headers=auth_headers).get_json()
        for i in range(5)
    ]
    expected_order = [t["id"] for t in reversed(created)]

    seen_ids = []
    cursor = None
    for _ in range(10):  # safety bound against infinite loop on a bug
        url = "/tasks?limit=2" + (f"&cursor={cursor}" if cursor is not None else "")
        body = client.get(url, headers=auth_headers).get_json()
        seen_ids.extend(t["id"] for t in body["data"])
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert seen_ids == expected_order


def test_list_tasks_limit_clamped_to_max(client, auth_headers):
    client.post("/tasks", json={"title": "only task"}, headers=auth_headers)
    resp = client.get("/tasks?limit=1000", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["data"]) == 1


def test_list_tasks_non_positive_limit_falls_back_to_default(client, auth_headers):
    resp = client.get("/tasks?limit=0", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["total"] == 0


def test_list_tasks_pagination_is_scoped_per_user(client, auth_headers):
    client.post("/tasks", json={"title": "alice task"}, headers=auth_headers)
    bob_headers = other_auth_headers(client)
    client.post("/tasks", json={"title": "bob task 1"}, headers=bob_headers)
    client.post("/tasks", json={"title": "bob task 2"}, headers=bob_headers)

    alice_body = client.get("/tasks", headers=auth_headers).get_json()
    bob_body = client.get("/tasks?limit=1", headers=bob_headers).get_json()

    assert alice_body["total"] == 1
    assert bob_body["total"] == 2
    assert len(bob_body["data"]) == 1
    assert bob_body["next_cursor"] is not None


def test_get_task(client, auth_headers):
    created = client.post("/tasks", json={"title": "task"}, headers=auth_headers).get_json()
    resp = client.get(f"/tasks/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == created["id"]
    assert data["title"] == "task"
    assert data["status"] == "pending"


def test_get_task_not_found(client, auth_headers):
    resp = client.get("/tasks/999", headers=auth_headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client, auth_headers):
    created = client.post("/tasks", json={"title": "old"}, headers=auth_headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "new"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "new"
    assert data["status"] == "pending"


def test_update_task_status(client, auth_headers):
    created = client.post("/tasks", json={"title": "task"}, headers=auth_headers).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "done"
    assert data["title"] == "task"


def test_update_task_title_and_status(client, auth_headers):
    created = client.post("/tasks", json={"title": "task"}, headers=auth_headers).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "renamed", "status": "done"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "renamed"
    assert data["status"] == "done"


def test_update_task_not_found(client, auth_headers):
    resp = client.put("/tasks/999", json={"title": "x"}, headers=auth_headers)
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_ids_assigned_manually_incrementing(client, auth_headers):
    t1 = client.post("/tasks", json={"title": "a"}, headers=auth_headers).get_json()
    t2 = client.post("/tasks", json={"title": "b"}, headers=auth_headers).get_json()
    assert t2["id"] == t1["id"] + 1


# ── Migration: pre-existing data without owner_id ────────────


def test_migration_preserves_existing_tasks_without_owner(client, tmp_path):
    """Simulates a pre-auth database: a tasks table with no owner_id column."""
    import sqlite3

    legacy_db = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(legacy_db)
    conn.execute(
        "CREATE TABLE tasks ("
        "  id INTEGER PRIMARY KEY,"
        "  title TEXT NOT NULL,"
        "  status TEXT NOT NULL DEFAULT 'pending',"
        "  created_at TEXT NOT NULL"
        ")"
    )
    conn.execute(
        "INSERT INTO tasks (id, title, status, created_at) VALUES (1, 'legacy task', 'pending', '2020-01-01T00:00:00')"
    )
    conn.commit()
    conn.close()

    app_module.DATABASE = legacy_db
    app_module.init_db()

    conn = sqlite3.connect(legacy_db)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM tasks WHERE id = 1").fetchone()
    conn.close()

    assert row["title"] == "legacy task"
    assert row["owner_id"] is None


# ── Notifications: completion trigger ────────────────────────


def test_completing_task_triggers_notification_email(client, auth_headers):
    created = client.post("/tasks", json={"title": "Ship report"}, headers=auth_headers).get_json()
    with patch("app.send_notification_email") as mock_task:
        resp = client.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth_headers
        )
    assert resp.status_code == 200
    mock_task.delay.assert_called_once_with("alice@example.com", "Ship report")


def test_notification_uses_registered_email(client):
    client.post(
        "/auth/register",
        json={"username": "carol", "password": "pw", "email": "carol@example.org"},
    )
    token = client.post(
        "/auth/login", json={"username": "carol", "password": "pw"}
    ).get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post("/tasks", json={"title": "ship it"}, headers=headers).get_json()
    with patch("app.send_notification_email") as mock_task:
        client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers)
    mock_task.delay.assert_called_once_with("carol@example.org", "ship it")


def test_updating_title_only_does_not_trigger_notification(client, auth_headers):
    created = client.post("/tasks", json={"title": "task"}, headers=auth_headers).get_json()
    with patch("app.send_notification_email") as mock_task:
        client.put(f"/tasks/{created['id']}", json={"title": "renamed"}, headers=auth_headers)
    mock_task.delay.assert_not_called()


def test_changing_status_to_non_completed_does_not_trigger_notification(client, auth_headers):
    created = client.post("/tasks", json={"title": "task"}, headers=auth_headers).get_json()
    with patch("app.send_notification_email") as mock_task:
        client.put(f"/tasks/{created['id']}", json={"status": "in_progress"}, headers=auth_headers)
    mock_task.delay.assert_not_called()


def test_recompleting_task_does_not_retrigger_notification(client, auth_headers):
    created = client.post("/tasks", json={"title": "task"}, headers=auth_headers).get_json()
    client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth_headers)
    with patch("app.send_notification_email") as mock_task:
        client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=auth_headers)
    mock_task.delay.assert_not_called()


def test_updating_nonexistent_task_does_not_trigger_notification(client, auth_headers):
    with patch("app.send_notification_email") as mock_task:
        resp = client.put("/tasks/999", json={"status": "completed"}, headers=auth_headers)
    assert resp.status_code == 404
    mock_task.delay.assert_not_called()


def test_completing_other_users_task_does_not_trigger_notification(client, auth_headers):
    created = client.post("/tasks", json={"title": "alice task"}, headers=auth_headers).get_json()
    bob_headers = other_auth_headers(client)
    with patch("app.send_notification_email") as mock_task:
        resp = client.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=bob_headers
        )
    assert resp.status_code == 404
    mock_task.delay.assert_not_called()


def test_send_notification_email_task_returns_sent_payload():
    result = app_module.send_notification_email.run("alice@example.com", "Ship report")
    assert result == {
        "user_email": "alice@example.com",
        "task_title": "Ship report",
        "sent": True,
    }


# ── Rate limiting ─────────────────────────────────────────────

RATE_LIMIT_PER_MINUTE = 100


def test_rate_limit_config_is_100_per_minute():
    assert app_module.RATE_LIMIT == "100 per minute"


def test_requests_within_limit_all_succeed(client, auth_headers):
    for _ in range(10):
        resp = client.get("/tasks", headers=auth_headers)
        assert resp.status_code == 200


def test_authenticated_user_blocked_after_limit_exceeded(client, auth_headers):
    last_resp = None
    for _ in range(RATE_LIMIT_PER_MINUTE + 1):
        last_resp = client.get("/tasks", headers=auth_headers)
    assert last_resp.status_code == 429
    assert "error" in last_resp.get_json()
    assert "Retry-After" in last_resp.headers
    assert int(last_resp.headers["Retry-After"]) >= 0


def test_unauthenticated_auth_endpoint_blocked_after_limit_exceeded(client):
    last_resp = None
    for _ in range(RATE_LIMIT_PER_MINUTE + 1):
        last_resp = client.post(
            "/auth/login", json={"username": "nobody", "password": "wrong"}
        )
    assert last_resp.status_code == 429
    assert "Retry-After" in last_resp.headers


def test_rate_limit_is_scoped_per_user(client, auth_headers):
    for _ in range(RATE_LIMIT_PER_MINUTE):
        resp = client.get("/tasks", headers=auth_headers)
        assert resp.status_code == 200

    bob_headers = other_auth_headers(client)
    resp = client.get("/tasks", headers=bob_headers)
    assert resp.status_code == 200
