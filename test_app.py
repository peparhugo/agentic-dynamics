import sqlite3
from unittest.mock import patch

import pytest
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter

from app import app, init_db, limiter


@pytest.fixture()
def client(tmp_path):
    app.config.update(
        TESTING=True,
        DATABASE=str(tmp_path / "tasks.db"),
        JWT_SECRET="test-secret",
        RATELIMIT_STORAGE_URI="memory://",
    )
    limiter._storage = MemoryStorage()
    limiter._limiter = FixedWindowRateLimiter(limiter._storage)
    init_db()
    return app.test_client()


def register_and_login(client, username="alice", password="password"):
    response = client.post("/auth/register", json={"username": username, "password": password})
    assert response.status_code == 201
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def create(client, title, headers):
    response = client.post("/tasks", json={"title": title}, headers=headers)
    assert response.status_code == 201
    return response.get_json()


def test_create_task_defaults_to_pending(client):
    task = create(client, "Write tests", register_and_login(client))

    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]


@pytest.mark.parametrize("payload", [{}, {"title": ""}, {"title": 3}])
def test_create_requires_a_title(client, payload):
    response = client.post("/tasks", json=payload, headers=register_and_login(client))

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_is_newest_first(client):
    headers = register_and_login(client)
    older = create(client, "Older", headers)
    newer = create(client, "Newer", headers)

    response = client.get("/tasks", headers=headers)

    assert response.status_code == 200
    body = response.get_json()
    assert [task["id"] for task in body["data"]] == [newer["id"], older["id"]]
    assert body == {"data": body["data"], "next_cursor": None, "total": 2}


def test_get_and_update_task(client):
    headers = register_and_login(client)
    task = create(client, "Draft", headers)

    update_response = client.put(
        f"/tasks/{task['id']}", json={"title": "Published", "status": "done"}, headers=headers
    )

    assert update_response.status_code == 200
    assert update_response.get_json()["title"] == "Published"
    assert update_response.get_json()["status"] == "done"
    assert client.get(f"/tasks/{task['id']}", headers=headers).get_json() == update_response.get_json()


def test_completing_a_task_enqueues_an_email_notification(client):
    headers = register_and_login(client)
    task = create(client, "Send report", headers)

    with patch("app.send_notification_email.delay") as delay:
        response = client.put(
            f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers
        )

    assert response.status_code == 200
    delay.assert_called_once_with("alice@example.com", "Send report")


def test_recompleting_a_task_does_not_enqueue_another_notification(client):
    headers = register_and_login(client)
    task = create(client, "Send report", headers)

    with patch("app.send_notification_email.delay") as delay:
        client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)
        client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)

    delay.assert_called_once_with("alice@example.com", "Send report")


def test_missing_task_returns_json_404(client):
    response = client.get("/tasks/999", headers=register_and_login(client))

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_update_requires_at_least_one_supported_field(client):
    headers = register_and_login(client)
    task = create(client, "Task", headers)

    response = client.put(f"/tasks/{task['id']}", json={}, headers=headers)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title or status is required"}


def test_register_hashes_password_and_rejects_duplicate_username(client):
    response = client.post("/auth/register", json={"username": "alice", "password": "password"})
    assert response.status_code == 201
    assert response.get_json() == {"username": "alice"}

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        password_hash = connection.execute("SELECT password_hash FROM users").fetchone()[0]
    assert password_hash != "password"

    response = client.post("/auth/register", json={"username": "alice", "password": "another"})
    assert response.status_code == 409


def test_login_rejects_invalid_credentials(client):
    register_and_login(client)
    response = client.post("/auth/login", json={"username": "alice", "password": "wrong"})
    assert response.status_code == 401
    assert response.get_json() == {"error": "invalid credentials"}


def test_tasks_require_a_valid_token(client):
    for response in (client.get("/tasks"), client.get("/tasks", headers={"Authorization": "Bearer invalid"})):
        assert response.status_code == 401
        assert response.get_json() == {"error": "authentication required"}


def test_users_only_see_and_modify_their_own_tasks(client):
    alice_headers = register_and_login(client, "alice")
    alice_task = create(client, "Alice task", alice_headers)
    bob_headers = register_and_login(client, "bob")
    create(client, "Bob task", bob_headers)

    assert [task["title"] for task in client.get("/tasks", headers=bob_headers).get_json()["data"]] == ["Bob task"]
    assert client.get(f"/tasks/{alice_task['id']}", headers=bob_headers).status_code == 404
    assert client.put(f"/tasks/{alice_task['id']}", json={"status": "done"}, headers=bob_headers).status_code == 404


def test_existing_task_database_is_migrated_without_losing_rows(tmp_path):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO tasks (title, status, created_at) VALUES ('Legacy', 'pending', 'now')")

    app.config.update(TESTING=True, DATABASE=str(database))
    init_db()

    with sqlite3.connect(database) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(tasks)")]
        task = connection.execute("SELECT title, owner_id FROM tasks").fetchone()
    assert "owner_id" in columns
    assert task == ("Legacy", None)


def test_list_tasks_uses_cursor_pagination(client):
    headers = register_and_login(client)
    tasks = [create(client, f"Task {index}", headers) for index in range(3)]

    first_page = client.get("/tasks?limit=2", headers=headers)

    assert first_page.status_code == 200
    assert first_page.get_json()["data"] == [tasks[2], tasks[1]]
    assert first_page.get_json()["next_cursor"] == str(tasks[1]["id"])
    assert first_page.get_json()["total"] == 3

    second_page = client.get(f"/tasks?limit=2&cursor={tasks[1]['id']}", headers=headers)

    assert second_page.get_json() == {"data": [tasks[0]], "next_cursor": None, "total": 3}


@pytest.mark.parametrize("query", ["?limit=0", "?limit=101", "?limit=bad", "?cursor=0"])
def test_list_tasks_rejects_invalid_pagination(client, query):
    response = client.get(f"/tasks{query}", headers=register_and_login(client))

    assert response.status_code == 400


def test_rate_limit_is_enforced_per_authenticated_user(client):
    headers = register_and_login(client)

    for _ in range(100):
        assert client.get("/tasks", headers=headers).status_code == 200
    response = client.get("/tasks", headers=headers)

    assert response.status_code == 429
    assert response.headers["Retry-After"]
