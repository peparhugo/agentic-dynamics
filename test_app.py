import sqlite3
from unittest.mock import patch

from app import create_app


def make_client(tmp_path):
    app = create_app(str(tmp_path / "tasks.db"), limiter_storage_uri="memory://")
    app.config["JWT_SECRET"] = "test-secret"
    return app.test_client()


def register_and_login(client, username="alice", password="password"):
    response = client.post("/auth/register", json={"username": username, "password": password})
    assert response.status_code == 201
    response = client.post("/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def test_register_and_login_return_a_token(tmp_path):
    client = make_client(tmp_path)

    registered = client.post("/auth/register", json={"username": "alice", "password": "password"})
    logged_in = client.post("/auth/login", json={"username": "alice", "password": "password"})

    assert registered.status_code == 201
    assert registered.get_json() == {"id": 1, "username": "alice"}
    assert logged_in.status_code == 200
    assert logged_in.get_json()["token"]


def test_register_rejects_duplicate_username_and_login_rejects_bad_password(tmp_path):
    client = make_client(tmp_path)
    register_and_login(client)

    duplicate = client.post("/auth/register", json={"username": "alice", "password": "other"})
    bad_login = client.post("/auth/login", json={"username": "alice", "password": "wrong"})

    assert duplicate.status_code == 409
    assert bad_login.status_code == 401


def test_tasks_require_a_valid_token(tmp_path):
    client = make_client(tmp_path)

    missing = client.get("/tasks")
    invalid = client.post("/tasks", json={"title": "Nope"}, headers={"Authorization": "Bearer invalid"})

    assert missing.status_code == 401
    assert invalid.status_code == 401


def test_create_task_uses_pending_status_and_returns_task(tmp_path):
    client = make_client(tmp_path)
    headers = register_and_login(client)

    response = client.post("/tasks", json={"title": "Write tests"}, headers=headers)

    assert response.status_code == 201
    task = response.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]


def test_create_task_requires_title(tmp_path):
    client = make_client(tmp_path)
    headers = register_and_login(client)

    response = client.post("/tasks", json={}, headers=headers)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_is_newest_first(tmp_path):
    client = make_client(tmp_path)
    headers = register_and_login(client)
    first = client.post("/tasks", json={"title": "First"}, headers=headers).get_json()
    second = client.post("/tasks", json={"title": "Second"}, headers=headers).get_json()

    response = client.get("/tasks", headers=headers)

    assert response.status_code == 200
    body = response.get_json()
    assert [task["id"] for task in body["data"]] == [second["id"], first["id"]]
    assert body["next_cursor"] is None
    assert body["total"] == 2


def test_get_and_update_task(tmp_path):
    client = make_client(tmp_path)
    headers = register_and_login(client)
    task = client.post("/tasks", json={"title": "Old title"}, headers=headers).get_json()

    update = client.put(
        f"/tasks/{task['id']}", json={"title": "New title", "status": "done"}, headers=headers
    )
    retrieved = client.get(f"/tasks/{task['id']}", headers=headers)

    assert update.status_code == 200
    assert update.get_json()["title"] == "New title"
    assert update.get_json()["status"] == "done"
    assert retrieved.get_json() == update.get_json()


def test_completing_task_queues_owner_notification(tmp_path):
    client = make_client(tmp_path)
    headers = register_and_login(client)
    task = client.post("/tasks", json={"title": "Email owner"}, headers=headers).get_json()

    with patch("app.send_notification_email.delay") as delay:
        response = client.put(
            f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers
        )

    assert response.status_code == 200
    delay.assert_called_once_with("alice", "Email owner")


def test_completed_task_does_not_send_duplicate_notification(tmp_path):
    client = make_client(tmp_path)
    headers = register_and_login(client)
    task = client.post("/tasks", json={"title": "Already complete"}, headers=headers).get_json()
    client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)

    with patch("app.send_notification_email.delay") as delay:
        response = client.put(
            f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers
        )

    assert response.status_code == 200
    delay.assert_not_called()


def test_users_only_see_and_change_their_own_tasks(tmp_path):
    client = make_client(tmp_path)
    alice_headers = register_and_login(client, "alice")
    task = client.post("/tasks", json={"title": "Alice task"}, headers=alice_headers).get_json()
    bob_headers = register_and_login(client, "bob")

    listed = client.get("/tasks", headers=bob_headers)
    fetched = client.get(f"/tasks/{task['id']}", headers=bob_headers)
    updated = client.put(f"/tasks/{task['id']}", json={"status": "done"}, headers=bob_headers)

    assert listed.get_json() == {"data": [], "next_cursor": None, "total": 0}
    assert fetched.status_code == 404
    assert updated.status_code == 404


def test_task_migration_preserves_existing_rows(tmp_path):
    database = tmp_path / "tasks.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES ('Legacy', 'pending', '2020-01-01')"
        )

    create_app(str(database))

    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(tasks)")}
        legacy_task = connection.execute("SELECT title, owner_id FROM tasks WHERE id = 1").fetchone()
    assert "owner_id" in columns
    assert legacy_task == ("Legacy", None)


def test_missing_task_returns_json_404(tmp_path):
    client = make_client(tmp_path)
    headers = register_and_login(client)

    response = client.get("/tasks/99", headers=headers)

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_list_tasks_uses_cursor_pagination(tmp_path):
    client = make_client(tmp_path)
    headers = register_and_login(client)
    created = [
        client.post("/tasks", json={"title": f"Task {number}"}, headers=headers).get_json()
        for number in range(3)
    ]

    first_page = client.get("/tasks?limit=2", headers=headers)
    first_body = first_page.get_json()
    second_page = client.get(f"/tasks?cursor={first_body['next_cursor']}&limit=2", headers=headers)

    assert first_page.status_code == 200
    assert [task["id"] for task in first_body["data"]] == [created[2]["id"], created[1]["id"]]
    assert first_body["next_cursor"] == str(created[1]["id"])
    assert first_body["total"] == 3
    assert second_page.get_json() == {
        "data": [created[0]],
        "next_cursor": None,
        "total": 3,
    }


def test_list_tasks_rejects_invalid_pagination_parameters(tmp_path):
    client = make_client(tmp_path)
    headers = register_and_login(client)

    invalid_cursor = client.get("/tasks?cursor=zero", headers=headers)
    invalid_limit = client.get("/tasks?limit=101", headers=headers)

    assert invalid_cursor.status_code == 400
    assert invalid_limit.status_code == 400


def test_rate_limit_returns_retry_after_header(tmp_path):
    client = make_client(tmp_path)
    headers = register_and_login(client)

    responses = [client.get("/tasks", headers=headers) for _ in range(101)]

    assert responses[-2].status_code == 200
    assert responses[-1].status_code == 429
    assert responses[-1].headers["Retry-After"]
