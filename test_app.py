import sqlite3
from unittest.mock import patch

import jwt
import pytest
from werkzeug.security import check_password_hash

import app as task_app


@pytest.fixture()
def client(tmp_path):
    application = task_app.create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "tasks.db"),
            "JWT_SECRET_KEY": "test-secret",
            "RATELIMIT_STORAGE_URI": "memory://",
        }
    )
    return application.test_client()


@pytest.fixture()
def auth_headers(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    token = client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    ).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_get_task(client, auth_headers):
    response = client.post(
        "/tasks", json={"title": "Write tests"}, headers=auth_headers
    )

    assert response.status_code == 201
    task = response.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]

    assert client.get("/tasks/1", headers=auth_headers).get_json() == task


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "   "}])
def test_create_requires_title(client, auth_headers, body):
    response = client.post("/tasks", json=body, headers=auth_headers)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_first_page_newest_first(client, auth_headers):
    first = client.post(
        "/tasks", json={"title": "First"}, headers=auth_headers
    ).get_json()
    second = client.post(
        "/tasks", json={"title": "Second"}, headers=auth_headers
    ).get_json()

    response = client.get("/tasks", headers=auth_headers)

    assert response.status_code == 200
    assert response.get_json() == {
        "data": [second, first],
        "next_cursor": None,
        "total": 2,
    }


def test_list_tasks_uses_cursor_pagination(client, auth_headers):
    tasks = [
        client.post(
            "/tasks", json={"title": f"Task {number}"}, headers=auth_headers
        ).get_json()
        for number in range(5)
    ]

    first_page = client.get("/tasks?limit=2", headers=auth_headers).get_json()
    second_page = client.get(
        f"/tasks?limit=2&cursor={first_page['next_cursor']}", headers=auth_headers
    ).get_json()
    final_page = client.get(
        f"/tasks?limit=2&cursor={second_page['next_cursor']}", headers=auth_headers
    ).get_json()

    assert first_page == {
        "data": [tasks[4], tasks[3]],
        "next_cursor": str(tasks[3]["id"]),
        "total": 5,
    }
    assert second_page == {
        "data": [tasks[2], tasks[1]],
        "next_cursor": str(tasks[1]["id"]),
        "total": 5,
    }
    assert final_page == {"data": [tasks[0]], "next_cursor": None, "total": 5}


@pytest.mark.parametrize(
    ("query", "error"),
    [
        ("cursor=abc", "cursor and limit must be integers"),
        ("cursor=0", "cursor must be a positive integer"),
        ("limit=0", "limit must be between 1 and 100"),
        ("limit=101", "limit must be between 1 and 100"),
    ],
)
def test_list_tasks_rejects_invalid_pagination(client, auth_headers, query, error):
    response = client.get(f"/tasks?{query}", headers=auth_headers)

    assert response.status_code == 400
    assert response.get_json() == {"error": error}


def test_update_title_and_status(client, auth_headers):
    task_id = client.post(
        "/tasks", json={"title": "Draft"}, headers=auth_headers
    ).get_json()["id"]

    response = client.put(
        f"/tasks/{task_id}",
        json={"title": "Final", "status": "completed"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "Final"
    assert response.get_json()["status"] == "completed"


def test_update_single_field(client, auth_headers):
    task_id = client.post(
        "/tasks", json={"title": "Task"}, headers=auth_headers
    ).get_json()["id"]

    response = client.put(
        f"/tasks/{task_id}", json={"status": "in-progress"}, headers=auth_headers
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "Task"
    assert response.get_json()["status"] == "in-progress"


def test_completing_task_queues_notification(client, auth_headers):
    task_id = client.post(
        "/tasks", json={"title": "Ship release"}, headers=auth_headers
    ).get_json()["id"]

    with patch("app.send_notification_email.delay") as delay:
        response = client.put(
            f"/tasks/{task_id}",
            json={"status": "completed"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    delay.assert_called_once_with("alice", "Ship release")


def test_notification_only_queued_on_transition_to_completed(client, auth_headers):
    task_id = client.post(
        "/tasks", json={"title": "Finished task"}, headers=auth_headers
    ).get_json()["id"]
    client.put(
        f"/tasks/{task_id}", json={"status": "completed"}, headers=auth_headers
    )

    with patch("app.send_notification_email.delay") as delay:
        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Renamed task", "status": "completed"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    delay.assert_not_called()


def test_non_completed_status_does_not_queue_notification(client, auth_headers):
    task_id = client.post(
        "/tasks", json={"title": "Ongoing task"}, headers=auth_headers
    ).get_json()["id"]

    with patch("app.send_notification_email.delay") as delay:
        response = client.put(
            f"/tasks/{task_id}",
            json={"status": "in-progress"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    delay.assert_not_called()


@pytest.mark.parametrize("method", ["get", "put"])
def test_missing_task_returns_404(client, auth_headers, method):
    if method == "get":
        response = client.get("/tasks/999", headers=auth_headers)
    else:
        response = client.put(
            "/tasks/999", json={"status": "completed"}, headers=auth_headers
        )

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_update_requires_supported_field(client, auth_headers):
    task_id = client.post(
        "/tasks", json={"title": "Task"}, headers=auth_headers
    ).get_json()["id"]

    response = client.put(f"/tasks/{task_id}", json={}, headers=auth_headers)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title or status is required"}


def test_register_stores_password_hash(client):
    response = client.post(
        "/auth/register", json={"username": "bob", "password": "plain-text"}
    )

    assert response.status_code == 201
    assert response.get_json() == {"id": 1, "username": "bob"}
    with task_app.get_db() as connection:
        user = connection.execute("SELECT * FROM users WHERE username = 'bob'").fetchone()
    assert user["password_hash"] != "plain-text"
    assert check_password_hash(user["password_hash"], "plain-text")


def test_register_rejects_duplicate_username(client):
    credentials = {"username": "alice", "password": "secret"}
    assert client.post("/auth/register", json=credentials).status_code == 201

    response = client.post("/auth/register", json=credentials)

    assert response.status_code == 409
    assert response.get_json() == {"error": "username already exists"}


@pytest.mark.parametrize(
    "credentials",
    [
        {"username": "unknown", "password": "secret"},
        {"username": "alice", "password": "wrong"},
    ],
)
def test_login_rejects_invalid_credentials(client, credentials):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})

    response = client.post("/auth/login", json=credentials)

    assert response.status_code == 401
    assert response.get_json() == {"error": "invalid credentials"}


def test_login_returns_valid_jwt(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})

    response = client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    )

    assert response.status_code == 200
    token = response.get_json()["token"]
    payload = jwt.decode(token, "test-secret", algorithms=["HS256"])
    assert payload["sub"] == "1"
    assert payload["exp"] > payload["iat"]


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer invalid"}, {"Authorization": "Token abc"}],
)
def test_tasks_require_valid_token(client, headers):
    response = client.get("/tasks", headers=headers)

    assert response.status_code == 401


def test_users_only_see_and_modify_their_own_tasks(client, auth_headers):
    alice_task = client.post(
        "/tasks", json={"title": "Alice task"}, headers=auth_headers
    ).get_json()
    client.post("/auth/register", json={"username": "bob", "password": "secret"})
    bob_token = client.post(
        "/auth/login", json={"username": "bob", "password": "secret"}
    ).get_json()["token"]
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    assert client.get("/tasks", headers=bob_headers).get_json() == {
        "data": [],
        "next_cursor": None,
        "total": 0,
    }
    assert client.get(f"/tasks/{alice_task['id']}", headers=bob_headers).status_code == 404
    assert (
        client.put(
            f"/tasks/{alice_task['id']}",
            json={"status": "completed"},
            headers=bob_headers,
        ).status_code
        == 404
    )


def test_init_db_migrates_existing_tasks_without_data_loss(tmp_path):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', "
            "created_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO tasks (title, created_at) VALUES ('Legacy', '2020-01-01')"
        )

    task_app.create_app(
        {
            "TESTING": True,
            "DATABASE": str(database),
            "RATELIMIT_STORAGE_URI": "memory://",
        }
    )

    with sqlite3.connect(database) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(tasks)")]
        task = connection.execute("SELECT title, owner_id FROM tasks").fetchone()
    assert "owner_id" in columns
    assert task == ("Legacy", None)


def test_authenticated_user_is_rate_limited_with_retry_after(tmp_path):
    application = task_app.create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "rate-limit.db"),
            "JWT_SECRET_KEY": "test-secret",
            "RATELIMIT_DEFAULT": "2 per minute",
            "RATELIMIT_STORAGE_URI": "memory://",
        }
    )
    client = application.test_client()
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    token = client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    ).get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/tasks", headers=headers).status_code == 200
    assert client.get("/tasks", headers=headers).status_code == 200
    response = client.get("/tasks", headers=headers)

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


def test_rate_limit_applies_to_auth_endpoints(tmp_path):
    application = task_app.create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "auth-rate-limit.db"),
            "RATELIMIT_DEFAULT": "1 per minute",
            "RATELIMIT_STORAGE_URI": "memory://",
        }
    )
    client = application.test_client()

    assert client.post("/auth/register", json={}).status_code == 400
    response = client.post("/auth/login", json={})

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
