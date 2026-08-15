import json
from datetime import datetime
from unittest.mock import patch

import jwt
import pytest
from werkzeug.security import check_password_hash

from app import create_app


@pytest.fixture
def data_file(tmp_path):
    return tmp_path / "tasks.json"


@pytest.fixture
def users_file(tmp_path):
    return tmp_path / "users.json"


@pytest.fixture
def app(data_file, users_file):
    return create_app(
        {
            "TESTING": True,
            "TASKS_FILE": str(data_file),
            "USERS_FILE": str(users_file),
            "JWT_SECRET_KEY": "test-secret-key-at-least-32-bytes-long",
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


def register_and_login(client, username="alice", password="correct horse"):
    registered = client.post(
        "/auth/register", json={"username": username, "password": password}
    )
    assert registered.status_code == 201
    logged_in = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert logged_in.status_code == 200
    return {
        "Authorization": f"Bearer {logged_in.json['token']}"
    }, registered.json


@pytest.fixture
def auth(client):
    headers, _ = register_and_login(client)
    return headers


def test_storage_is_initialized(data_file, users_file):
    create_app(
        {
            "TESTING": True,
            "TASKS_FILE": str(data_file),
            "USERS_FILE": str(users_file),
        }
    )
    assert json.loads(data_file.read_text()) == []
    assert json.loads(users_file.read_text()) == []


def test_legacy_tasks_are_migrated_without_data_loss(data_file, users_file):
    legacy_task = {
        "id": 7,
        "title": "Legacy",
        "status": "pending",
        "created_at": "2025-01-01T00:00:00+00:00",
    }
    data_file.write_text(json.dumps([legacy_task]))

    create_app(
        {
            "TESTING": True,
            "TASKS_FILE": str(data_file),
            "USERS_FILE": str(users_file),
        }
    )

    assert json.loads(data_file.read_text()) == [{**legacy_task, "owner_id": None}]


def test_register_creates_user_with_hashed_password(client, users_file):
    response = client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    )

    assert response.status_code == 201
    assert response.json == {"id": 1, "username": "alice"}
    stored_user = json.loads(users_file.read_text())[0]
    assert stored_user["password_hash"] != "secret"
    assert check_password_hash(stored_user["password_hash"], "secret")


@pytest.mark.parametrize(
    "body",
    [{}, {"username": ""}, {"username": "alice"}, {"password": "secret"}, None],
)
def test_register_requires_username_and_password(client, body):
    response = client.post("/auth/register", json=body)

    assert response.status_code == 400
    assert response.json == {"error": "username and password are required"}


def test_duplicate_username_is_rejected(client):
    body = {"username": "alice", "password": "secret"}
    assert client.post("/auth/register", json=body).status_code == 201

    response = client.post("/auth/register", json=body)

    assert response.status_code == 409
    assert response.json == {"error": "username already exists"}


def test_login_returns_valid_jwt(client, app):
    client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    )

    response = client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    )

    assert response.status_code == 200
    payload = jwt.decode(
        response.json["token"], app.config["JWT_SECRET_KEY"], algorithms=["HS256"]
    )
    assert payload["sub"] == "1"
    assert "iat" in payload
    assert "exp" in payload


@pytest.mark.parametrize(
    "body",
    [
        {"username": "alice", "password": "wrong"},
        {"username": "missing", "password": "secret"},
    ],
)
def test_login_rejects_invalid_credentials(client, body):
    client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    )

    response = client.post("/auth/login", json=body)

    assert response.status_code == 401
    assert response.json == {"error": "invalid username or password"}


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/tasks"),
        ("get", "/tasks"),
        ("get", "/tasks/1"),
        ("put", "/tasks/1"),
    ],
)
def test_task_endpoints_require_authentication(client, method, path):
    response = getattr(client, method)(path, json={"title": "Task"})

    assert response.status_code == 401


@pytest.mark.parametrize(
    "authorization", ["Bearer not-a-jwt", "Basic credentials", "Bearer"]
)
def test_invalid_authorization_is_rejected(client, authorization):
    response = client.get("/tasks", headers={"Authorization": authorization})

    assert response.status_code == 401


def test_create_task(client, auth):
    response = client.post("/tasks", json={"title": "Write tests"}, headers=auth)

    assert response.status_code == 201
    assert response.json["id"] == 1
    assert response.json["title"] == "Write tests"
    assert response.json["status"] == "pending"
    assert response.json["owner_id"] == 1
    datetime.fromisoformat(response.json["created_at"])


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "   "}, None])
def test_create_requires_title(client, auth, body):
    response = client.post("/tasks", json=body, headers=auth)

    assert response.status_code == 400
    assert response.json == {"error": "title is required"}


def test_list_tasks_newest_first(client, auth):
    first = client.post("/tasks", json={"title": "First"}, headers=auth).json
    second = client.post("/tasks", json={"title": "Second"}, headers=auth).json

    response = client.get("/tasks", headers=auth)

    assert response.status_code == 200
    assert response.json == [second, first]


def test_get_task_and_missing_task(client, auth):
    task = client.post("/tasks", json={"title": "Existing"}, headers=auth).json

    assert client.get(f"/tasks/{task['id']}", headers=auth).json == task
    missing = client.get("/tasks/999", headers=auth)
    assert missing.status_code == 404
    assert missing.json == {"error": "task not found"}


def test_update_title_and_status(client, auth):
    task = client.post("/tasks", json={"title": "Old title"}, headers=auth).json

    response = client.put(
        f"/tasks/{task['id']}",
        json={"title": "New title", "status": "done"},
        headers=auth,
    )

    assert response.status_code == 200
    assert response.json["title"] == "New title"
    assert response.json["status"] == "done"
    assert response.json["created_at"] == task["created_at"]


def test_update_one_field(client, auth):
    task = client.post("/tasks", json={"title": "Task"}, headers=auth).json

    response = client.put(
        f"/tasks/{task['id']}", json={"status": "active"}, headers=auth
    )

    assert response.json["title"] == "Task"
    assert response.json["status"] == "active"


def test_completed_status_transition_enqueues_notification(client):
    auth, _ = register_and_login(client, "owner@example.com")
    task = client.post(
        "/tasks", json={"title": "Ship release"}, headers=auth
    ).json

    with patch("app.send_notification_email.delay") as delay:
        response = client.put(
            f"/tasks/{task['id']}",
            json={"status": "completed"},
            headers=auth,
        )

    assert response.status_code == 200
    delay.assert_called_once_with("owner@example.com", "Ship release")


def test_completed_status_without_transition_does_not_enqueue_notification(
    client, auth
):
    task = client.post("/tasks", json={"title": "Task"}, headers=auth).json

    with patch("app.send_notification_email.delay") as delay:
        first = client.put(
            f"/tasks/{task['id']}", json={"status": "completed"}, headers=auth
        )
        delay.reset_mock()
        second = client.put(
            f"/tasks/{task['id']}", json={"status": "completed"}, headers=auth
        )

    assert first.status_code == 200
    assert second.status_code == 200
    delay.assert_not_called()


def test_update_validates_body_and_missing_task(client, auth):
    task = client.post("/tasks", json={"title": "Task"}, headers=auth).json

    invalid = client.put(
        f"/tasks/{task['id']}", json={"title": " "}, headers=auth
    )
    assert invalid.status_code == 400
    assert "error" in invalid.json

    missing = client.put("/tasks/999", json={"status": "done"}, headers=auth)
    assert missing.status_code == 404
    assert missing.json == {"error": "task not found"}


def test_users_only_see_and_modify_their_own_tasks(client):
    alice_auth, _ = register_and_login(client, "alice")
    alice_task = client.post(
        "/tasks", json={"title": "Alice task"}, headers=alice_auth
    ).json
    bob_auth, _ = register_and_login(client, "bob")
    bob_task = client.post(
        "/tasks", json={"title": "Bob task"}, headers=bob_auth
    ).json

    assert client.get("/tasks", headers=alice_auth).json == [alice_task]
    assert client.get("/tasks", headers=bob_auth).json == [bob_task]
    assert client.get(f"/tasks/{alice_task['id']}", headers=bob_auth).status_code == 404
    assert (
        client.put(
            f"/tasks/{alice_task['id']}",
            json={"status": "done"},
            headers=bob_auth,
        ).status_code
        == 404
    )


def test_tasks_and_users_persist_between_app_instances(data_file, users_file):
    config = {
        "TESTING": True,
        "TASKS_FILE": str(data_file),
        "USERS_FILE": str(users_file),
        "JWT_SECRET_KEY": "persistent-secret-at-least-32-bytes-long",
    }
    first_client = create_app(config).test_client()
    headers, _ = register_and_login(first_client)
    created = first_client.post(
        "/tasks", json={"title": "Persistent"}, headers=headers
    ).json

    second_client = create_app(config).test_client()
    logged_in = second_client.post(
        "/auth/login", json={"username": "alice", "password": "correct horse"}
    )
    second_headers = {"Authorization": f"Bearer {logged_in.json['token']}"}
    assert second_client.get("/tasks", headers=second_headers).json == [created]
