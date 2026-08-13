import sqlite3

import app as task_app
import pytest


@pytest.fixture()
def client(tmp_path):
    database = tmp_path / "tasks.sqlite"
    task_app.app.config.update(
        TESTING=True, DATABASE=str(database), JWT_SECRET_KEY="test-secret"
    )
    task_app.limiter.reset()
    task_app.init_db()
    return task_app.app.test_client()


def register(client, username="alice", password="secret"):
    return client.post("/auth/register", json={"username": username, "password": password})


def auth_headers(client, username="alice", password="secret"):
    register(client, username, password)
    response = client.post("/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def test_register_creates_user_with_hashed_password(client):
    response = register(client)

    assert response.status_code == 201
    assert response.get_json() == {"id": 1, "username": "alice"}
    with sqlite3.connect(task_app.app.config["DATABASE"]) as connection:
        password_hash = connection.execute("SELECT password_hash FROM users").fetchone()[0]
    assert password_hash != "secret"


def test_register_rejects_duplicate_username(client):
    register(client)

    response = register(client)

    assert response.status_code == 409
    assert response.get_json() == {"error": "username already exists"}


def test_login_returns_token_and_rejects_bad_credentials(client):
    register(client)

    response = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    bad_response = client.post("/auth/login", json={"username": "alice", "password": "wrong"})

    assert response.status_code == 200
    assert response.get_json()["token"]
    assert bad_response.status_code == 401
    assert bad_response.get_json() == {"error": "invalid credentials"}


def test_tasks_require_a_valid_token(client):
    for method, path in ((client.get, "/tasks"), (client.post, "/tasks"), (client.get, "/tasks/1"), (client.put, "/tasks/1")):
        response = method(path, json={"title": "Task"}) if method in (client.post, client.put) else method(path)
        assert response.status_code == 401
        assert response.get_json() == {"error": "authentication required"}

    response = client.get("/tasks", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401


def test_create_task_uses_defaults(client):
    response = client.post("/tasks", json={"title": "Write tests"}, headers=auth_headers(client))

    assert response.status_code == 201
    task = response.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]


def test_create_task_requires_title(client):
    response = client.post("/tasks", json={}, headers=auth_headers(client))

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_is_newest_first(client):
    headers = auth_headers(client)
    first = client.post("/tasks", json={"title": "First"}, headers=headers).get_json()
    second = client.post("/tasks", json={"title": "Second"}, headers=headers).get_json()

    response = client.get("/tasks", headers=headers)

    assert response.status_code == 200
    assert response.get_json() == {
        "data": [second, first],
        "next_cursor": None,
        "total": 2,
    }


def test_list_tasks_uses_cursor_pagination(client):
    headers = auth_headers(client)
    tasks = [
        client.post("/tasks", json={"title": f"Task {number}"}, headers=headers).get_json()
        for number in range(3)
    ]

    first_page = client.get("/tasks?limit=2", headers=headers)

    assert first_page.status_code == 200
    assert first_page.get_json() == {
        "data": [tasks[2], tasks[1]],
        "next_cursor": str(tasks[1]["id"]),
        "total": 3,
    }
    second_page = client.get(
        f"/tasks?cursor={tasks[1]['id']}&limit=2", headers=headers
    )
    assert second_page.get_json() == {
        "data": [tasks[0]],
        "next_cursor": None,
        "total": 3,
    }


@pytest.mark.parametrize("query", ("?limit=0", "?limit=101", "?limit=no", "?cursor=no"))
def test_list_tasks_rejects_invalid_pagination(client, query):
    response = client.get(f"/tasks{query}", headers=auth_headers(client))

    assert response.status_code == 400


def test_authenticated_user_is_rate_limited(client):
    headers = auth_headers(client)

    for _ in range(100):
        assert client.get("/tasks", headers=headers).status_code == 200
    response = client.get("/tasks", headers=headers)

    assert response.status_code == 429
    assert response.headers["Retry-After"]


def test_auth_endpoints_are_rate_limited(client):
    for _ in range(100):
        assert client.post("/auth/login", json={}).status_code == 401

    response = client.post("/auth/login", json={})

    assert response.status_code == 429
    assert response.headers["Retry-After"]


def test_users_only_see_and_change_their_own_tasks(client):
    alice_headers = auth_headers(client, "alice")
    bob_headers = auth_headers(client, "bob")
    task = client.post("/tasks", json={"title": "Private"}, headers=alice_headers).get_json()

    assert client.get("/tasks", headers=bob_headers).get_json() == {
        "data": [],
        "next_cursor": None,
        "total": 0,
    }
    assert client.get(f"/tasks/{task['id']}", headers=bob_headers).status_code == 404
    assert client.put(f"/tasks/{task['id']}", json={"status": "done"}, headers=bob_headers).status_code == 404
    assert client.get(f"/tasks/{task['id']}", headers=alice_headers).get_json() == task


def test_get_task_and_missing_task(client):
    headers = auth_headers(client)
    task = client.post("/tasks", json={"title": "Read"}, headers=headers).get_json()

    assert client.get(f"/tasks/{task['id']}", headers=headers).get_json() == task
    missing = client.get("/tasks/999", headers=headers)
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "task not found"}


def test_update_task_title_and_status(client):
    headers = auth_headers(client)
    task = client.post("/tasks", json={"title": "Draft"}, headers=headers).get_json()

    response = client.put(
        f"/tasks/{task['id']}", json={"title": "Published", "status": "done"}, headers=headers
    )

    assert response.status_code == 200
    assert response.get_json() == {**task, "title": "Published", "status": "done"}


def test_completing_a_task_enqueues_notification(client, monkeypatch):
    client.post(
        "/auth/register",
        json={"username": "notify", "password": "secret", "email": "notify@example.com"},
    )
    notify_headers = client.post(
        "/auth/login", json={"username": "notify", "password": "secret"}
    ).get_json()
    notify_headers = {"Authorization": f"Bearer {notify_headers['token']}"}
    task = client.post("/tasks", json={"title": "Email me"}, headers=notify_headers).get_json()
    calls = []
    monkeypatch.setattr(task_app.send_notification_email, "delay", lambda *args: calls.append(args))

    response = client.put(
        f"/tasks/{task['id']}", json={"status": "completed"}, headers=notify_headers
    )

    assert response.status_code == 200
    assert calls == [("notify@example.com", "Email me")]


def test_notification_is_not_enqueued_without_a_completion_transition(client, monkeypatch):
    client.post(
        "/auth/register",
        json={"username": "notify", "password": "secret", "email": "notify@example.com"},
    )
    login_response = client.post(
        "/auth/login", json={"username": "notify", "password": "secret"}
    ).get_json()
    headers = {"Authorization": f"Bearer {login_response['token']}"}
    task = client.post("/tasks", json={"title": "No duplicate"}, headers=headers).get_json()
    calls = []
    monkeypatch.setattr(task_app.send_notification_email, "delay", lambda *args: calls.append(args))

    client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)
    client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)

    assert calls == [("notify@example.com", "No duplicate")]


def test_update_missing_task_returns_json_404(client):
    response = client.put("/tasks/999", json={"status": "done"}, headers=auth_headers(client))

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_init_db_migrates_existing_tasks_without_data_loss(tmp_path):
    database = tmp_path / "legacy.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES ('Legacy', 'pending', '2026-01-01T00:00:00+00:00')"
        )
    task_app.app.config["DATABASE"] = str(database)

    task_app.init_db()

    with sqlite3.connect(database) as connection:
        row = connection.execute("SELECT title, owner_id FROM tasks").fetchone()
    assert row == ("Legacy", None)
