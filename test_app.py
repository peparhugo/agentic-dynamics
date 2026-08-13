import app as task_app
import sqlite3
from limits.storage import storage_from_string
from limits.strategies import FixedWindowRateLimiter


def configure_database(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    monkeypatch.setattr(task_app, "JWT_SECRET", "test-secret")
    task_app.limiter._storage = storage_from_string("memory://")
    task_app.limiter._limiter = FixedWindowRateLimiter(task_app.limiter._storage)
    task_app.init_db()
    return task_app.app.test_client()


def auth_headers(client, username="alice", password="secret"):
    client.post("/auth/register", json={"username": username, "password": password})
    response = client.post("/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def auth_headers_with_email(client, username="alice", password="secret"):
    client.post(
        "/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": password},
    )
    response = client.post("/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def test_create_task_uses_pending_status_and_returns_task(tmp_path, monkeypatch):
    client = configure_database(tmp_path, monkeypatch)

    response = client.post("/tasks", json={"title": "Write tests"}, headers=auth_headers(client))

    assert response.status_code == 201
    task = response.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]


def test_create_task_requires_title(tmp_path, monkeypatch):
    client = configure_database(tmp_path, monkeypatch)

    response = client.post("/tasks", json={}, headers=auth_headers(client))

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_is_paginated_newest_first(tmp_path, monkeypatch):
    client = configure_database(tmp_path, monkeypatch)
    headers = auth_headers(client)
    client.post("/tasks", json={"title": "First"}, headers=headers)
    client.post("/tasks", json={"title": "Second"}, headers=headers)

    response = client.get("/tasks", headers=headers)

    assert response.status_code == 200
    assert [task["title"] for task in response.get_json()["data"]] == ["Second", "First"]
    assert response.get_json()["next_cursor"] is None
    assert response.get_json()["total"] == 2


def test_get_and_update_task(tmp_path, monkeypatch):
    client = configure_database(tmp_path, monkeypatch)
    headers = auth_headers(client)
    task_id = client.post("/tasks", json={"title": "Draft"}, headers=headers).get_json()["id"]

    update = client.put(
        f"/tasks/{task_id}", json={"title": "Publish", "status": "complete"}, headers=headers
    )
    fetched = client.get(f"/tasks/{task_id}", headers=headers)

    assert update.status_code == 200
    assert update.get_json()["title"] == "Publish"
    assert update.get_json()["status"] == "complete"
    assert fetched.status_code == 200
    assert fetched.get_json() == update.get_json()


def test_completing_task_queues_notification_once(tmp_path, monkeypatch):
    client = configure_database(tmp_path, monkeypatch)
    headers = auth_headers_with_email(client)
    task_id = client.post("/tasks", json={"title": "Send report"}, headers=headers).get_json()["id"]
    queued = []
    monkeypatch.setattr(task_app.send_notification_email, "delay", lambda *args: queued.append(args))

    completed = client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)
    unchanged = client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)

    assert completed.status_code == 200
    assert unchanged.status_code == 200
    assert queued == [("alice@example.com", "Send report")]


def test_missing_task_returns_json_404(tmp_path, monkeypatch):
    client = configure_database(tmp_path, monkeypatch)
    headers = auth_headers(client)

    get_response = client.get("/tasks/999", headers=headers)
    update_response = client.put("/tasks/999", json={"status": "complete"}, headers=headers)

    assert get_response.status_code == 404
    assert get_response.get_json() == {"error": "task not found"}
    assert update_response.status_code == 404
    assert update_response.get_json() == {"error": "task not found"}


def test_register_login_and_reject_duplicate_user(tmp_path, monkeypatch):
    client = configure_database(tmp_path, monkeypatch)

    registered = client.post("/auth/register", json={"username": "alice", "password": "secret"})
    duplicate = client.post("/auth/register", json={"username": "alice", "password": "other"})
    login = client.post("/auth/login", json={"username": "alice", "password": "secret"})

    assert registered.status_code == 201
    assert registered.get_json() == {"id": 1, "username": "alice"}
    assert duplicate.status_code == 409
    assert login.status_code == 200
    assert login.get_json()["token"]


def test_login_rejects_invalid_credentials(tmp_path, monkeypatch):
    client = configure_database(tmp_path, monkeypatch)
    client.post("/auth/register", json={"username": "alice", "password": "secret"})

    response = client.post("/auth/login", json={"username": "alice", "password": "wrong"})

    assert response.status_code == 401
    assert response.get_json() == {"error": "invalid credentials"}


def test_tasks_require_a_valid_token(tmp_path, monkeypatch):
    client = configure_database(tmp_path, monkeypatch)

    missing = client.get("/tasks")
    invalid = client.post("/tasks", json={"title": "Nope"}, headers={"Authorization": "Bearer invalid"})

    assert missing.status_code == 401
    assert invalid.status_code == 401


def test_users_can_only_access_their_own_tasks(tmp_path, monkeypatch):
    client = configure_database(tmp_path, monkeypatch)
    alice_headers = auth_headers(client, "alice")
    bob_headers = auth_headers(client, "bob")
    task_id = client.post("/tasks", json={"title": "Private"}, headers=alice_headers).get_json()["id"]

    listed = client.get("/tasks", headers=bob_headers)
    fetched = client.get(f"/tasks/{task_id}", headers=bob_headers)
    updated = client.put(f"/tasks/{task_id}", json={"status": "complete"}, headers=bob_headers)

    assert listed.get_json() == {"data": [], "next_cursor": None, "total": 0}
    assert fetched.status_code == 404
    assert updated.status_code == 404


def test_init_db_migrates_existing_tasks_without_losing_data(tmp_path, monkeypatch):
    database = tmp_path / "tasks.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, "
            "status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
            ("Existing task", "pending", "2026-01-01T00:00:00+00:00"),
        )

    monkeypatch.setattr(task_app, "DATABASE", str(database))
    task_app.init_db()

    with sqlite3.connect(database) as connection:
        task = connection.execute("SELECT title, owner_id FROM tasks WHERE id = 1").fetchone()
        users_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'users'"
        ).fetchone()

    assert task == ("Existing task", None)
    assert users_table == ("users",)


def test_list_tasks_uses_id_cursor_and_limit(tmp_path, monkeypatch):
    client = configure_database(tmp_path, monkeypatch)
    headers = auth_headers(client)
    for title in ("First", "Second", "Third"):
        client.post("/tasks", json={"title": title}, headers=headers)

    first_page = client.get("/tasks?limit=2", headers=headers)
    first_body = first_page.get_json()
    second_page = client.get(f"/tasks?cursor={first_body['next_cursor']}&limit=2", headers=headers)

    assert first_page.status_code == 200
    assert [task["title"] for task in first_body["data"]] == ["Third", "Second"]
    assert first_body["next_cursor"] == "2"
    assert first_body["total"] == 3
    second_body = second_page.get_json()
    assert [task["title"] for task in second_body["data"]] == ["First"]
    assert second_body["next_cursor"] is None
    assert second_body["total"] == 3


def test_list_tasks_rejects_invalid_pagination_parameters(tmp_path, monkeypatch):
    client = configure_database(tmp_path, monkeypatch)
    headers = auth_headers(client)

    invalid_cursor = client.get("/tasks?cursor=invalid", headers=headers)
    invalid_limit = client.get("/tasks?limit=101", headers=headers)

    assert invalid_cursor.status_code == 400
    assert invalid_limit.status_code == 400


def test_rate_limit_returns_retry_after_header(tmp_path, monkeypatch):
    client = configure_database(tmp_path, monkeypatch)
    headers = auth_headers(client)
    task_app.limiter.reset()

    responses = [client.get("/tasks", headers=headers) for _ in range(101)]

    assert all(response.status_code == 200 for response in responses[:100])
    assert responses[-1].status_code == 429
    assert int(responses[-1].headers["Retry-After"]) >= 0


def test_rate_limit_applies_to_auth_endpoints(tmp_path, monkeypatch):
    client = configure_database(tmp_path, monkeypatch)
    task_app.limiter.reset()

    responses = [
        client.post("/auth/login", json={"username": "missing", "password": "secret"})
        for _ in range(101)
    ]

    assert all(response.status_code == 401 for response in responses[:100])
    assert responses[-1].status_code == 429
    assert "Retry-After" in responses[-1].headers
