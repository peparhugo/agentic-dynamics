import json

import pytest

import app as task_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    data_file = tmp_path / "tasks.json"
    monkeypatch.setattr(task_app, "DATA_FILE", data_file)
    task_app.init_storage()
    return task_app.app.test_client()


@pytest.fixture
def auth_client(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    token = client.post("/auth/login", json={"username": "alice", "password": "secret"}).json["token"]
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client


def test_create_task_defaults_status_and_lists_newest_first(auth_client):
    first = auth_client.post("/tasks", json={"title": "First"})
    second = auth_client.post("/tasks", json={"title": "Second"})

    assert first.status_code == 201
    assert first.json["status"] == "pending"
    assert [task["title"] for task in auth_client.get("/tasks").json] == ["Second", "First"]


def test_create_requires_title(auth_client):
    response = auth_client.post("/tasks", json={})

    assert response.status_code == 400
    assert response.json == {"error": "title is required"}


def test_get_and_update_task(auth_client):
    created = auth_client.post("/tasks", json={"title": "Old title"}).json

    response = auth_client.put(
        f"/tasks/{created['id']}",
        json={"title": "New title", "status": "complete"},
    )

    assert response.status_code == 200
    assert response.json["title"] == "New title"
    assert response.json["status"] == "complete"
    assert auth_client.get(f"/tasks/{created['id']}").json == response.json


def test_missing_task_returns_json_404(auth_client):
    response = auth_client.get("/tasks/123")

    assert response.status_code == 404
    assert response.json == {"error": "task not found"}


def test_storage_is_a_json_flat_file(auth_client, tmp_path, monkeypatch):
    auth_client.post("/tasks", json={"title": "Persisted"})

    data_file = task_app.DATA_FILE
    assert data_file.suffix == ".json"
    assert json.loads(data_file.read_text())["tasks"][0]["title"] == "Persisted"


def test_tasks_require_authentication(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "Private"}).status_code == 401


def test_users_only_see_their_own_tasks(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    alice_token = client.post("/auth/login", json={"username": "alice", "password": "secret"}).json["token"]
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {alice_token}"
    task = client.post("/tasks", json={"title": "Alice's task"}).json

    client.post("/auth/register", json={"username": "bob", "password": "secret"})
    bob_token = client.post("/auth/login", json={"username": "bob", "password": "secret"}).json["token"]
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {bob_token}"
    assert client.get("/tasks").json == []
    assert client.get(f"/tasks/{task['id']}").status_code == 404


def test_register_login_and_duplicate_username(client):
    response = client.post("/auth/register", json={"username": "alice", "password": "secret"})
    assert response.status_code == 201
    assert "password_hash" not in response.json
    assert client.post("/auth/register", json={"username": "alice", "password": "other"}).status_code == 409
    assert client.post("/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401
    assert "token" in client.post("/auth/login", json={"username": "alice", "password": "secret"}).json
