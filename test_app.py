import pytest
from unittest.mock import Mock

import app as app_module
from app import app, init_db


@pytest.fixture()
def client(tmp_path):
    app.config.update(TESTING=True, TASKS_FILE=str(tmp_path / "tasks.json"))
    init_db()
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture()
def auth_client(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    token = client.post("/auth/login", json={"username": "alice", "password": "secret"}).get_json()["token"]
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client


def test_create_and_list_tasks(auth_client):
    response = auth_client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    task = response.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert auth_client.get("/tasks").get_json() == [task]


def test_create_requires_title(auth_client):
    response = auth_client.post("/tasks", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_get_update_and_missing_task(auth_client):
    auth_client.post("/tasks", json={"title": "Old title"})

    response = auth_client.put("/tasks/1", json={"title": "New title", "status": "done"})
    assert response.status_code == 200
    assert response.get_json()["title"] == "New title"
    assert response.get_json()["status"] == "done"
    assert auth_client.get("/tasks/1").get_json()["title"] == "New title"

    missing = auth_client.get("/tasks/99")
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "task not found"}


def test_completing_task_queues_owner_notification(client, monkeypatch):
    client.post(
        "/auth/register",
        json={"username": "alice", "password": "secret", "email": "alice@example.com"},
    )
    token = client.post("/auth/login", json={"username": "alice", "password": "secret"}).get_json()["token"]
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    client.post("/tasks", json={"title": "Ship feature"})
    queue = Mock()
    monkeypatch.setattr(app_module.send_notification_email, "delay", queue)

    response = client.put("/tasks/1", json={"status": "completed"})

    assert response.status_code == 200
    queue.assert_called_once_with("alice@example.com", "Ship feature")


def test_notification_only_runs_on_completion_transition(auth_client, monkeypatch):
    auth_client.post("/tasks", json={"title": "Ship feature"})
    queue = Mock()
    monkeypatch.setattr(app_module.send_notification_email, "delay", queue)

    auth_client.put("/tasks/1", json={"status": "in progress"})
    auth_client.put("/tasks/1", json={"status": "completed"})
    auth_client.put("/tasks/1", json={"title": "Updated title"})

    queue.assert_called_once_with("alice", "Ship feature")


def test_tasks_require_a_valid_token(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "No access"}).status_code == 401
    client.environ_base["HTTP_AUTHORIZATION"] = "Bearer invalid"
    assert client.get("/tasks").status_code == 401


def test_register_and_login(client):
    registered = client.post("/auth/register", json={"username": "alice", "password": "secret"})
    assert registered.status_code == 201
    assert registered.get_json() == {"id": 1, "username": "alice"}
    assert client.post("/auth/register", json={"username": "alice", "password": "other"}).status_code == 409
    login = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    assert login.status_code == 200
    assert isinstance(login.get_json()["token"], str)
    assert client.post("/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401


def test_users_only_see_their_own_tasks(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    alice_token = client.post("/auth/login", json={"username": "alice", "password": "secret"}).get_json()["token"]
    client.post("/auth/register", json={"username": "bob", "password": "secret"})
    bob_token = client.post("/auth/login", json={"username": "bob", "password": "secret"}).get_json()["token"]

    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {alice_token}"
    client.post("/tasks", json={"title": "Alice task"})
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {bob_token}"
    assert client.get("/tasks").get_json() == []
    assert client.get("/tasks/1").status_code == 404
