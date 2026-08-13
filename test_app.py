import sqlite3

import app as task_app
import pytest
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter
from werkzeug.security import check_password_hash


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "test.db"))
    storage = MemoryStorage()
    monkeypatch.setattr(task_app.limiter, "_storage", storage)
    monkeypatch.setattr(task_app.limiter, "_limiter", FixedWindowRateLimiter(storage))
    task_app.app.config.update(
        TESTING=True,
        JWT_SECRET="test-secret",
        JWT_EXPIRATION_SECONDS=3600,
    )
    task_app.init_db()
    return task_app.app.test_client()


def register(client, username="alice", password="secret", email=None):
    body = {"username": username, "password": password}
    if email is not None:
        body["email"] = email
    return client.post("/auth/register", json=body)


def auth_headers(client, username="alice", password="secret", email=None):
    if register(client, username, password, email).status_code not in (201, 409):
        raise AssertionError("could not create test user")
    response = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def test_register_creates_user_with_hashed_password(client):
    response = register(client)

    assert response.status_code == 201
    assert response.get_json()["username"] == "alice"
    with task_app.get_db() as connection:
        user = connection.execute(
            "SELECT username, password_hash FROM users WHERE username = 'alice'"
        ).fetchone()
    assert user["password_hash"] != "secret"
    assert check_password_hash(user["password_hash"], "secret")


@pytest.mark.parametrize(
    "body",
    [{}, {"username": ""}, {"username": "alice"}, {"password": "secret"}],
)
def test_register_requires_credentials(client, body):
    assert client.post("/auth/register", json=body).status_code == 400


def test_register_rejects_duplicate_username(client):
    assert register(client).status_code == 201
    assert register(client).status_code == 409


def test_login_returns_jwt_for_valid_credentials(client):
    register(client)

    response = client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    )

    assert response.status_code == 200
    assert len(response.get_json()["token"].split(".")) == 3


@pytest.mark.parametrize(
    "body",
    [
        {"username": "missing", "password": "secret"},
        {"username": "alice", "password": "wrong"},
    ],
)
def test_login_rejects_invalid_credentials(client, body):
    register(client)
    assert client.post("/auth/login", json=body).status_code == 401


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer invalid"}, {"Authorization": "Basic abc"}],
)
def test_tasks_require_valid_token(client, headers):
    assert client.get("/tasks", headers=headers).status_code == 401
    assert client.post("/tasks", json={"title": "Task"}, headers=headers).status_code == 401
    assert client.get("/tasks/1", headers=headers).status_code == 401
    assert client.put("/tasks/1", json={"status": "done"}, headers=headers).status_code == 401


def test_create_and_get_task(client):
    headers = auth_headers(client)
    response = client.post("/tasks", json={"title": "Write tests"}, headers=headers)

    assert response.status_code == 201
    task = response.get_json()
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]

    response = client.get(f"/tasks/{task['id']}", headers=headers)
    assert response.status_code == 200
    assert response.get_json() == task


def test_list_tasks_newest_first(client):
    headers = auth_headers(client)
    first = client.post("/tasks", json={"title": "First"}, headers=headers).get_json()
    second = client.post("/tasks", json={"title": "Second"}, headers=headers).get_json()

    response = client.get("/tasks", headers=headers)

    assert response.status_code == 200
    body = response.get_json()
    assert [task["id"] for task in body["data"]] == [second["id"], first["id"]]
    assert body["next_cursor"] is None
    assert body["total"] == 2


def test_list_tasks_uses_cursor_pagination(client):
    headers = auth_headers(client)
    tasks = [
        client.post("/tasks", json={"title": str(index)}, headers=headers).get_json()
        for index in range(5)
    ]

    first_page = client.get("/tasks?limit=2", headers=headers).get_json()
    second_page = client.get(
        f"/tasks?limit=2&cursor={first_page['next_cursor']}", headers=headers
    ).get_json()
    final_page = client.get(
        f"/tasks?limit=2&cursor={second_page['next_cursor']}", headers=headers
    ).get_json()

    assert [task["id"] for task in first_page["data"]] == [tasks[4]["id"], tasks[3]["id"]]
    assert [task["id"] for task in second_page["data"]] == [tasks[2]["id"], tasks[1]["id"]]
    assert [task["id"] for task in final_page["data"]] == [tasks[0]["id"]]
    assert first_page["total"] == second_page["total"] == final_page["total"] == 5
    assert final_page["next_cursor"] is None


@pytest.mark.parametrize(
    "query",
    ["cursor=invalid", "cursor=0", "limit=invalid", "limit=0", "limit=101"],
)
def test_list_tasks_rejects_invalid_pagination(client, query):
    response = client.get(f"/tasks?{query}", headers=auth_headers(client))

    assert response.status_code == 400


def test_update_task(client, monkeypatch):
    monkeypatch.setattr(task_app.send_notification_email, "delay", lambda *args: None)
    headers = auth_headers(client)
    task_id = client.post("/tasks", json={"title": "Old"}, headers=headers).get_json()["id"]

    response = client.put(
        f"/tasks/{task_id}",
        json={"title": "New", "status": "completed"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "New"
    assert response.get_json()["status"] == "completed"


def test_completing_task_queues_owner_notification(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        task_app.send_notification_email, "delay", lambda *args: calls.append(args)
    )
    headers = auth_headers(client, email="alice@example.com")
    task_id = client.post(
        "/tasks", json={"title": "Send report"}, headers=headers
    ).get_json()["id"]

    response = client.put(
        f"/tasks/{task_id}", json={"status": "completed"}, headers=headers
    )

    assert response.status_code == 200
    assert calls == [("alice@example.com", "Send report")]


def test_completed_task_is_not_notified_again(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        task_app.send_notification_email, "delay", lambda *args: calls.append(args)
    )
    headers = auth_headers(client)
    task_id = client.post(
        "/tasks", json={"title": "One notification"}, headers=headers
    ).get_json()["id"]

    client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)
    client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)

    assert calls == [("alice", "One notification")]


def test_non_completed_update_does_not_queue_notification(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        task_app.send_notification_email, "delay", lambda *args: calls.append(args)
    )
    headers = auth_headers(client)
    task_id = client.post(
        "/tasks", json={"title": "Still working"}, headers=headers
    ).get_json()["id"]

    response = client.put(
        f"/tasks/{task_id}", json={"status": "in-progress"}, headers=headers
    )

    assert response.status_code == 200
    assert calls == []


def test_users_only_see_and_modify_their_own_tasks(client):
    alice_headers = auth_headers(client, "alice")
    bob_headers = auth_headers(client, "bob")
    task = client.post(
        "/tasks", json={"title": "Alice only"}, headers=alice_headers
    ).get_json()

    assert client.get("/tasks", headers=bob_headers).get_json() == {
        "data": [],
        "next_cursor": None,
        "total": 0,
    }
    assert client.get(f"/tasks/{task['id']}", headers=bob_headers).status_code == 404
    assert client.put(
        f"/tasks/{task['id']}", json={"status": "stolen"}, headers=bob_headers
    ).status_code == 404
    assert client.get(f"/tasks/{task['id']}", headers=alice_headers).get_json()["status"] == "pending"


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "   "}, {"title": 1}])
def test_create_requires_title(client, body):
    response = client.post("/tasks", json=body, headers=auth_headers(client))

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_missing_tasks_return_404(client):
    headers = auth_headers(client)
    assert client.get("/tasks/999", headers=headers).status_code == 404
    assert client.put(
        "/tasks/999", json={"status": "done"}, headers=headers
    ).status_code == 404
    assert client.get("/tasks/999", headers=headers).get_json() == {"error": "task not found"}


def test_update_requires_valid_fields(client):
    headers = auth_headers(client)
    task_id = client.post("/tasks", json={"title": "Task"}, headers=headers).get_json()["id"]

    assert client.put(f"/tasks/{task_id}", json={}, headers=headers).status_code == 400
    assert client.put(
        f"/tasks/{task_id}", json={"title": ""}, headers=headers
    ).status_code == 400
    assert client.put(
        f"/tasks/{task_id}", json={"status": None}, headers=headers
    ).status_code == 400


def test_rate_limit_applies_to_authenticated_user(client):
    headers = auth_headers(client)

    for _ in range(100):
        assert client.get("/tasks", headers=headers).status_code == 200
    response = client.get("/tasks", headers=headers)

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


def test_rate_limit_applies_to_auth_endpoints(client):
    for _ in range(100):
        assert client.post("/auth/login", json={}).status_code == 400

    response = client.post("/auth/login", json={})

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


def test_init_db_migrates_existing_tasks_without_data_loss(tmp_path, monkeypatch):
    database = tmp_path / "old.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO tasks (title, created_at) VALUES ('Existing', '2026-01-01')"
        )
    monkeypatch.setattr(task_app, "DATABASE", str(database))

    task_app.init_db()

    with task_app.get_db() as connection:
        task = connection.execute("SELECT * FROM tasks").fetchone()
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(tasks)")}
    assert "owner_id" in columns
    assert task["title"] == "Existing"
    assert task["owner_id"] is None
