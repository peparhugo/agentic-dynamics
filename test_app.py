import os
import tempfile
from unittest.mock import patch

import pytest

import app as app_module


@pytest.fixture
def client():
    fd, path = tempfile.mkstemp()
    app_module.DATABASE = path
    app_module.app.config["TESTING"] = True
    app_module.init_db()
    # Rate limit counters live in Redis and persist across tests (and
    # across the low user ids that each fresh temp DB reissues), so reset
    # them before every test to keep tests independent of each other.
    app_module.limiter.reset()

    with app_module.app.test_client() as client:
        yield client

    os.close(fd)
    os.unlink(path)


def register(client, username="alice", password="hunter2"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="hunter2"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_headers(client, username="alice", password="hunter2"):
    register(client, username, password)
    token = login(client, username, password).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ── Auth: register ───────────────────────────────────────────

def test_register_creates_user(client):
    response = register(client)
    assert response.status_code == 201
    body = response.get_json()
    assert body["username"] == "alice"
    assert "id" in body
    assert "password" not in body
    assert "password_hash" not in body


def test_register_missing_username_returns_400(client):
    response = client.post("/auth/register", json={"password": "hunter2"})
    assert response.status_code == 400


def test_register_missing_password_returns_400(client):
    response = client.post("/auth/register", json={"username": "alice"})
    assert response.status_code == 400


def test_register_duplicate_username_returns_409(client):
    register(client)
    response = register(client)
    assert response.status_code == 409


def test_password_is_hashed_not_stored_plaintext(client):
    register(client)
    user = app_module.get_user_by_username("alice")
    assert user["password_hash"] != "hunter2"


# ── Auth: login ──────────────────────────────────────────────

def test_login_returns_token(client):
    register(client)
    response = login(client)
    assert response.status_code == 200
    assert "token" in response.get_json()


def test_login_wrong_password_returns_401(client):
    register(client)
    response = login(client, password="wrongpass")
    assert response.status_code == 401


def test_login_unknown_user_returns_401(client):
    response = login(client, username="ghost")
    assert response.status_code == 401


# ── Task endpoints require auth ─────────────────────────────

def test_list_tasks_without_token_returns_401(client):
    response = client.get("/tasks")
    assert response.status_code == 401


def test_post_task_without_token_returns_401(client):
    response = client.post("/tasks", json={"title": "Buy milk"})
    assert response.status_code == 401


def test_show_task_without_token_returns_401(client):
    response = client.get("/tasks/1")
    assert response.status_code == 401


def test_edit_task_without_token_returns_401(client):
    response = client.put("/tasks/1", json={"title": "Nope"})
    assert response.status_code == 401


def test_invalid_token_returns_401(client):
    response = client.get("/tasks", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 401


def test_malformed_auth_header_returns_401(client):
    response = client.get("/tasks", headers={"Authorization": "garbage"})
    assert response.status_code == 401


# ── Task endpoints (authenticated) ──────────────────────────

def test_post_missing_title_returns_400(client):
    headers = auth_headers(client)
    response = client.post("/tasks", json={}, headers=headers)
    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_post_blank_title_returns_400(client):
    headers = auth_headers(client)
    response = client.post("/tasks", json={"title": "   "}, headers=headers)
    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_post_no_body_returns_400(client):
    headers = auth_headers(client)
    response = client.post("/tasks", headers=headers)
    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_post_creates_task(client):
    headers = auth_headers(client)
    response = client.post("/tasks", json={"title": "Buy milk"}, headers=headers)
    assert response.status_code == 201
    body = response.get_json()
    assert body["title"] == "Buy milk"
    assert body["status"] == "pending"
    assert "id" in body
    assert "created_at" in body


def test_list_tasks(client):
    headers = auth_headers(client)
    client.post("/tasks", json={"title": "Task A"}, headers=headers)
    client.post("/tasks", json={"title": "Task B"}, headers=headers)

    response = client.get("/tasks", headers=headers)
    assert response.status_code == 200
    body = response.get_json()
    titles = {task["title"] for task in body["data"]}
    assert titles == {"Task A", "Task B"}
    assert body["total"] == 2
    assert body["next_cursor"] is None


def test_show_task(client):
    headers = auth_headers(client)
    created = client.post("/tasks", json={"title": "Read book"}, headers=headers).get_json()

    response = client.get(f"/tasks/{created['id']}", headers=headers)
    assert response.status_code == 200
    assert response.get_json()["title"] == "Read book"


def test_show_task_not_found(client):
    headers = auth_headers(client)
    response = client.get("/tasks/999", headers=headers)
    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_edit_task(client):
    headers = auth_headers(client)
    created = client.post("/tasks", json={"title": "Old title"}, headers=headers).get_json()

    response = client.put(
        f"/tasks/{created['id']}",
        json={"title": "New title", "status": "done"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["title"] == "New title"
    assert body["status"] == "done"


def test_edit_task_not_found(client):
    headers = auth_headers(client)
    response = client.put("/tasks/999", json={"title": "Nope"}, headers=headers)
    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


# ── Per-user task isolation ──────────────────────────────────

def test_users_only_see_their_own_tasks(client):
    alice_headers = auth_headers(client, "alice", "pw-alice")
    bob_headers = auth_headers(client, "bob", "pw-bob")

    client.post("/tasks", json={"title": "Alice task"}, headers=alice_headers)
    client.post("/tasks", json={"title": "Bob task"}, headers=bob_headers)

    alice_titles = {t["title"] for t in client.get("/tasks", headers=alice_headers).get_json()["data"]}
    bob_titles = {t["title"] for t in client.get("/tasks", headers=bob_headers).get_json()["data"]}

    assert alice_titles == {"Alice task"}
    assert bob_titles == {"Bob task"}


def test_user_cannot_view_another_users_task(client):
    alice_headers = auth_headers(client, "alice", "pw-alice")
    bob_headers = auth_headers(client, "bob", "pw-bob")

    created = client.post("/tasks", json={"title": "Alice task"}, headers=alice_headers).get_json()

    response = client.get(f"/tasks/{created['id']}", headers=bob_headers)
    assert response.status_code == 404


def test_user_cannot_edit_another_users_task(client):
    alice_headers = auth_headers(client, "alice", "pw-alice")
    bob_headers = auth_headers(client, "bob", "pw-bob")

    created = client.post("/tasks", json={"title": "Alice task"}, headers=alice_headers).get_json()

    response = client.put(
        f"/tasks/{created['id']}", json={"title": "Hacked"}, headers=bob_headers
    )
    assert response.status_code == 404


# ── Migration: existing rows without owner_id ────────────────

def test_migration_adds_owner_id_column_to_existing_db(tmp_path):
    db_path = str(tmp_path / "legacy.db")

    import sqlite3

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

    conn = app_module.get_db()
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
    assert "owner_id" in columns

    row = conn.execute("SELECT * FROM tasks WHERE title = 'Legacy task'").fetchone()
    assert row["owner_id"] is None
    conn.close()


def test_migration_adds_email_column_to_existing_users_table(tmp_path):
    db_path = str(tmp_path / "legacy_users.db")

    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE users ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  username TEXT NOT NULL UNIQUE,"
        "  password_hash TEXT NOT NULL"
        ")"
    )
    conn.execute(
        "INSERT INTO users (username, password_hash) VALUES ('legacy', 'hash')"
    )
    conn.commit()
    conn.close()

    app_module.DATABASE = db_path
    app_module.init_db()

    conn = app_module.get_db()
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    assert "email" in columns

    row = conn.execute("SELECT * FROM users WHERE username = 'legacy'").fetchone()
    assert row["email"] is None
    conn.close()


# ── Registration email ──────────────────────────────────────

def test_register_defaults_email_from_username(client):
    response = register(client)
    body = response.get_json()
    assert body["email"] == "alice@example.com"


def test_register_with_custom_email(client):
    response = client.post(
        "/auth/register",
        json={"username": "alice", "password": "hunter2", "email": "alice@work.com"},
    )
    body = response.get_json()
    assert body["email"] == "alice@work.com"


# ── Async notification email on task completion ─────────────

def test_completing_task_triggers_notification_email(client):
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Ship feature"}, headers=headers
    ).get_json()

    with patch.object(app_module, "send_notification_email") as mock_task:
        response = client.put(
            f"/tasks/{created['id']}",
            json={"status": "completed"},
            headers=headers,
        )
        assert response.status_code == 200
        mock_task.delay.assert_called_once_with("alice@example.com", "Ship feature")


def test_completing_task_does_not_block_response_on_failure(client):
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Ship feature"}, headers=headers
    ).get_json()

    with patch.object(app_module, "send_notification_email") as mock_task:
        mock_task.delay.side_effect = RuntimeError("broker unreachable")
        with pytest.raises(RuntimeError):
            client.put(
                f"/tasks/{created['id']}",
                json={"status": "completed"},
                headers=headers,
            )


def test_non_completed_status_change_does_not_trigger_notification(client):
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Ship feature"}, headers=headers
    ).get_json()

    with patch.object(app_module, "send_notification_email") as mock_task:
        response = client.put(
            f"/tasks/{created['id']}",
            json={"status": "in_progress"},
            headers=headers,
        )
        assert response.status_code == 200
        mock_task.delay.assert_not_called()


def test_title_only_update_does_not_trigger_notification(client):
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Ship feature"}, headers=headers
    ).get_json()

    with patch.object(app_module, "send_notification_email") as mock_task:
        client.put(
            f"/tasks/{created['id']}", json={"title": "Ship it"}, headers=headers
        )
        mock_task.delay.assert_not_called()


def test_already_completed_task_does_not_retrigger_notification(client):
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Ship feature"}, headers=headers
    ).get_json()
    client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
    )

    with patch.object(app_module, "send_notification_email") as mock_task:
        client.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
        )
        mock_task.delay.assert_not_called()


def test_completing_nonexistent_task_does_not_trigger_notification(client):
    headers = auth_headers(client)

    with patch.object(app_module, "send_notification_email") as mock_task:
        response = client.put(
            "/tasks/999", json={"status": "completed"}, headers=headers
        )
        assert response.status_code == 404
        mock_task.delay.assert_not_called()


def test_completing_task_uses_custom_registered_email(client):
    client.post(
        "/auth/register",
        json={"username": "alice", "password": "hunter2", "email": "alice@work.com"},
    )
    headers = auth_headers(client)
    created = client.post(
        "/tasks", json={"title": "Ship feature"}, headers=headers
    ).get_json()

    with patch.object(app_module, "send_notification_email") as mock_task:
        client.put(
            f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
        )
        mock_task.delay.assert_called_once_with("alice@work.com", "Ship feature")


# ── Celery task logic (in-process, no broker needed) ─────────

def test_send_notification_email_task_prints_message(capsys):
    from notifications import send_notification_email

    result = send_notification_email("alice@example.com", "Ship feature")

    captured = capsys.readouterr()
    assert "alice@example.com" in captured.out
    assert "Ship feature" in captured.out
    assert "alice@example.com" in result
    assert "Ship feature" in result


# ── Pagination ────────────────────────────────────────────────

def seed_tasks(headers, count):
    """Create `count` tasks directly through the repository, bypassing HTTP
    so seeding large fixtures doesn't itself consume rate-limit budget."""
    user = app_module.user_repository.find_by_username("alice")
    for i in range(count):
        app_module.task_repository.create(title=f"Task {i}", owner_id=user["id"])


def test_list_tasks_empty_returns_empty_page(client):
    headers = auth_headers(client)
    response = client.get("/tasks", headers=headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body == {"data": [], "next_cursor": None, "total": 0}


def test_list_tasks_default_page_size_is_20(client):
    headers = auth_headers(client)
    seed_tasks(headers, 25)

    response = client.get("/tasks", headers=headers)
    body = response.get_json()
    assert response.status_code == 200
    assert len(body["data"]) == 20
    assert body["total"] == 25
    assert body["next_cursor"] is not None


def test_list_tasks_cursor_follows_to_next_page(client):
    headers = auth_headers(client)
    seed_tasks(headers, 25)

    first = client.get("/tasks", headers=headers).get_json()
    second = client.get(f"/tasks?cursor={first['next_cursor']}", headers=headers).get_json()

    assert len(second["data"]) == 5
    assert second["next_cursor"] is None
    assert second["total"] == 25
    first_ids = {t["id"] for t in first["data"]}
    second_ids = {t["id"] for t in second["data"]}
    assert first_ids.isdisjoint(second_ids)
    assert first_ids | second_ids == {t["id"] for t in first["data"] + second["data"]}


def test_list_tasks_cursor_is_id_of_last_item_in_page(client):
    headers = auth_headers(client)
    seed_tasks(headers, 3)

    response = client.get("/tasks?limit=2", headers=headers).get_json()
    assert response["next_cursor"] == str(response["data"][-1]["id"])


def test_list_tasks_respects_custom_limit(client):
    headers = auth_headers(client)
    seed_tasks(headers, 10)

    response = client.get("/tasks?limit=5", headers=headers)
    body = response.get_json()
    assert len(body["data"]) == 5
    assert body["next_cursor"] is not None


def test_list_tasks_limit_is_capped_at_100(client):
    headers = auth_headers(client)
    seed_tasks(headers, 150)

    response = client.get("/tasks?limit=500", headers=headers)
    body = response.get_json()
    assert len(body["data"]) == 100
    assert body["total"] == 150


def test_list_tasks_last_page_has_no_next_cursor(client):
    headers = auth_headers(client)
    seed_tasks(headers, 20)

    response = client.get("/tasks?limit=20", headers=headers)
    body = response.get_json()
    assert len(body["data"]) == 20
    assert body["next_cursor"] is None


def test_list_tasks_invalid_cursor_returns_400(client):
    headers = auth_headers(client)
    response = client.get("/tasks?cursor=not-a-number", headers=headers)
    assert response.status_code == 400


def test_list_tasks_invalid_limit_returns_400(client):
    headers = auth_headers(client)
    response = client.get("/tasks?limit=not-a-number", headers=headers)
    assert response.status_code == 400


def test_list_tasks_non_positive_limit_returns_400(client):
    headers = auth_headers(client)
    response = client.get("/tasks?limit=0", headers=headers)
    assert response.status_code == 400


def test_list_tasks_pagination_isolated_per_user(client):
    alice_headers = auth_headers(client, "alice", "pw-alice")
    seed_tasks(alice_headers, 5)
    bob_headers = auth_headers(client, "bob", "pw-bob")
    bob = app_module.user_repository.find_by_username("bob")
    app_module.task_repository.create(title="Bob task", owner_id=bob["id"])

    response = client.get("/tasks", headers=bob_headers).get_json()
    assert response["total"] == 1
    assert [t["title"] for t in response["data"]] == ["Bob task"]


# ── Rate limiting ────────────────────────────────────────────

def test_requests_within_limit_succeed(client):
    headers = auth_headers(client)
    for _ in range(10):
        response = client.get("/tasks", headers=headers)
        assert response.status_code == 200


def test_exceeding_rate_limit_returns_429_with_retry_after(client):
    headers = auth_headers(client)

    responses = [client.get("/tasks", headers=headers) for _ in range(101)]

    assert all(r.status_code == 200 for r in responses[:100])
    limited = responses[100]
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers
    assert limited.get_json() == {"error": "rate limit exceeded"}


def test_rate_limit_is_scoped_per_user(client):
    alice_headers = auth_headers(client, "alice", "pw-alice")
    for _ in range(100):
        client.get("/tasks", headers=alice_headers)
    # Alice is now at her limit.
    assert client.get("/tasks", headers=alice_headers).status_code == 429

    # Bob is a different rate-limit key and is unaffected.
    bob_headers = auth_headers(client, "bob", "pw-bob")
    assert client.get("/tasks", headers=bob_headers).status_code == 200


def test_auth_endpoints_are_rate_limited(client):
    responses = [
        client.post("/auth/login", json={"username": "nobody", "password": "wrong"})
        for _ in range(101)
    ]
    assert responses[100].status_code == 429
    assert "Retry-After" in responses[100].headers
