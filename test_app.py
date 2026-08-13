import sqlite3
from unittest.mock import Mock

import app as task_app
import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    task_app.app.config.update(
        TESTING=True, JWT_SECRET="test-secret", JWT_EXPIRATION_SECONDS=3600
    )
    return task_app.app.test_client()


def register_and_login(client, username="alice", password="secret"):
    register = client.post(
        "/auth/register", json={"username": username, "password": password}
    )
    assert register.status_code == 201
    login = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.get_json()['token']}"}


@pytest.fixture
def auth_headers(client):
    return register_and_login(client)


def test_register_creates_user_with_hashed_password(client):
    response = client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    )

    assert response.status_code == 201
    assert response.get_json()["username"] == "alice"
    with task_app.get_db() as connection:
        user = connection.execute(
            "SELECT username, password_hash FROM users WHERE username = 'alice'"
        ).fetchone()
    assert user["username"] == "alice"
    assert user["password_hash"] != "secret"


@pytest.mark.parametrize(
    ("body", "error"),
    [
        ({"password": "secret"}, "username is required"),
        ({"username": "alice"}, "password is required"),
        ({"username": " ", "password": "secret"}, "username is required"),
    ],
)
def test_register_validates_credentials(client, body, error):
    response = client.post("/auth/register", json=body)

    assert response.status_code == 400
    assert response.get_json() == {"error": error}


def test_duplicate_username_is_rejected(client):
    register_and_login(client)

    response = client.post(
        "/auth/register", json={"username": "alice", "password": "other"}
    )

    assert response.status_code == 409
    assert response.get_json() == {"error": "username already exists"}


@pytest.mark.parametrize(
    "credentials",
    [
        {"username": "alice", "password": "wrong"},
        {"username": "missing", "password": "secret"},
        {"username": "alice"},
    ],
)
def test_login_rejects_invalid_credentials(client, credentials):
    client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    )

    response = client.post("/auth/login", json=credentials)

    assert response.status_code == 401
    assert response.get_json() == {"error": "invalid username or password"}


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("get", "/tasks", {}),
        ("post", "/tasks", {"json": {"title": "Task"}}),
        ("get", "/tasks/1", {}),
        ("put", "/tasks/1", {"json": {"status": "done"}}),
    ],
)
def test_task_endpoints_require_authentication(client, method, path, kwargs):
    response = getattr(client, method)(path, **kwargs)

    assert response.status_code == 401


def test_invalid_and_expired_tokens_are_rejected(client):
    headers = register_and_login(client)
    invalid = client.get("/tasks", headers={"Authorization": "Bearer invalid"})

    task_app.app.config["JWT_EXPIRATION_SECONDS"] = -1
    expired_token = task_app.create_token(1)
    expired = client.get(
        "/tasks", headers={"Authorization": f"Bearer {expired_token}"}
    )

    assert invalid.status_code == 401
    assert expired.status_code == 401
    assert headers["Authorization"].startswith("Bearer ")


def test_create_and_get_task(client, auth_headers):
    response = client.post(
        "/tasks", json={"title": "Write tests"}, headers=auth_headers
    )

    assert response.status_code == 201
    task = response.get_json()
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]
    assert task["owner_id"]

    response = client.get(f"/tasks/{task['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json() == task


@pytest.mark.parametrize(
    "request_kwargs",
    [{"json": {}}, {"json": {"title": "  "}}, {"data": "not json"}],
)
def test_create_requires_title(client, auth_headers, request_kwargs):
    response = client.post("/tasks", headers=auth_headers, **request_kwargs)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_newest_first(client, auth_headers):
    first = client.post(
        "/tasks", json={"title": "First"}, headers=auth_headers
    ).get_json()
    second = client.post(
        "/tasks", json={"title": "Second"}, headers=auth_headers
    ).get_json()

    response = client.get("/tasks", headers=auth_headers)

    assert response.status_code == 200
    assert [task["id"] for task in response.get_json()] == [second["id"], first["id"]]


def test_update_task(client, auth_headers):
    task = client.post(
        "/tasks", json={"title": "Old"}, headers=auth_headers
    ).get_json()

    response = client.put(
        f"/tasks/{task['id']}",
        json={"title": "New", "status": "done"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "New"
    assert response.get_json()["status"] == "done"


def test_completing_task_enqueues_owner_notification(
    client, auth_headers, monkeypatch
):
    task = client.post(
        "/tasks", json={"title": "Ship release"}, headers=auth_headers
    ).get_json()
    delay = Mock()
    monkeypatch.setattr(task_app.send_notification_email, "delay", delay)

    response = client.put(
        f"/tasks/{task['id']}",
        json={"status": "completed"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    delay.assert_called_once_with("alice", "Ship release")


def test_notification_only_enqueued_on_transition_to_completed(
    client, auth_headers, monkeypatch
):
    task = client.post(
        "/tasks", json={"title": "Ship release"}, headers=auth_headers
    ).get_json()
    delay = Mock()
    monkeypatch.setattr(task_app.send_notification_email, "delay", delay)

    client.put(
        f"/tasks/{task['id']}", json={"status": "pending"}, headers=auth_headers
    )
    client.put(
        f"/tasks/{task['id']}", json={"status": "completed"}, headers=auth_headers
    )
    client.put(
        f"/tasks/{task['id']}", json={"status": "completed"}, headers=auth_headers
    )

    delay.assert_called_once_with("alice", "Ship release")


@pytest.mark.parametrize("method", ["get", "put"])
def test_missing_task_returns_404(client, auth_headers, method):
    kwargs = {"json": {"status": "done"}} if method == "put" else {}
    response = getattr(client, method)("/tasks/999", headers=auth_headers, **kwargs)

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_users_only_see_and_update_their_own_tasks(client):
    alice_headers = register_and_login(client, "alice")
    alice_task = client.post(
        "/tasks", json={"title": "Alice task"}, headers=alice_headers
    ).get_json()
    bob_headers = register_and_login(client, "bob")

    assert client.get("/tasks", headers=bob_headers).get_json() == []
    assert client.get(
        f"/tasks/{alice_task['id']}", headers=bob_headers
    ).status_code == 404
    assert client.put(
        f"/tasks/{alice_task['id']}",
        json={"status": "done"},
        headers=bob_headers,
    ).status_code == 404


def test_init_db_migrates_existing_tasks_without_data_loss(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
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
            "INSERT INTO tasks (title, created_at) VALUES ('Legacy', '2026-01-01')"
        )
    monkeypatch.setattr(task_app, "DATABASE", str(database))

    task_app.init_db()

    with task_app.get_db() as connection:
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(tasks)")
        }
        legacy_task = connection.execute(
            "SELECT title, owner_id FROM tasks WHERE title = 'Legacy'"
        ).fetchone()
    assert "owner_id" in columns
    assert dict(legacy_task) == {"title": "Legacy", "owner_id": None}
