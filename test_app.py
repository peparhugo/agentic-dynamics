import json

import app as task_app
import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.json"))
    task_app.init_db()
    task_app.app.config.update(TESTING=True)
    return task_app.app.test_client()


def auth_headers(client, username="alice", password="secret"):
    assert client.post("/auth/register", json={"username": username, "password": password}).status_code == 201
    response = client.post("/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {response.json['token']}"}


def test_create_task_and_default_fields(client):
    response = client.post("/tasks", json={"title": "Write tests"}, headers=auth_headers(client))

    assert response.status_code == 201
    assert response.json["id"] == 1
    assert response.json["title"] == "Write tests"
    assert response.json["status"] == "pending"
    assert response.json["created_at"]


def test_create_task_requires_title(client):
    response = client.post("/tasks", json={}, headers=auth_headers(client))

    assert response.status_code == 400
    assert response.json == {"error": "title is required"}


def test_list_tasks_is_newest_first(client):
    headers = auth_headers(client)
    client.post("/tasks", json={"title": "First"}, headers=headers)
    client.post("/tasks", json={"title": "Second"}, headers=headers)

    response = client.get("/tasks", headers=headers)

    assert response.status_code == 200
    assert [task["title"] for task in response.json] == ["Second", "First"]


def test_get_and_update_task(client):
    headers = auth_headers(client)
    task = client.post("/tasks", json={"title": "Original"}, headers=headers).json

    response = client.put(
        f"/tasks/{task['id']}", json={"title": "Updated", "status": "done"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json["title"] == "Updated"
    assert response.json["status"] == "done"
    assert client.get(f"/tasks/{task['id']}", headers=headers).json == response.json


def test_missing_task_returns_json_not_found_error(client):
    response = client.get("/tasks/99", headers=auth_headers(client))

    assert response.status_code == 404
    assert response.json == {"error": "task not found"}


def test_tasks_are_written_to_a_flat_file(client, tmp_path, monkeypatch):
    data_file = tmp_path / "persisted-tasks.json"
    monkeypatch.setattr(task_app, "DATABASE", str(data_file))
    task_app.init_db()

    client.post("/tasks", json={"title": "Persist me"}, headers=auth_headers(client))

    assert json.loads(data_file.read_text(encoding="utf-8"))["tasks"][0]["title"] == "Persist me"


def test_register_hashes_password_and_rejects_duplicate_usernames(client, tmp_path):
    assert client.post("/auth/register", json={"username": "alice", "password": "secret"}).status_code == 201
    assert client.post("/auth/register", json={"username": "alice", "password": "other"}).status_code == 409
    stored_user = json.loads((tmp_path / "tasks.json").read_text(encoding="utf-8"))["users"][0]
    assert stored_user["password_hash"] != "secret"


def test_login_rejects_invalid_credentials(client):
    auth_headers(client)
    response = client.post("/auth/login", json={"username": "alice", "password": "wrong"})
    assert response.status_code == 401


def test_tasks_require_a_valid_token(client):
    assert client.get("/tasks").status_code == 401
    assert client.get("/tasks", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_users_can_only_access_their_own_tasks(client):
    alice_headers = auth_headers(client, "alice")
    bob_headers = auth_headers(client, "bob")
    task = client.post("/tasks", json={"title": "Alice task"}, headers=alice_headers).json

    assert client.get("/tasks", headers=bob_headers).json == []
    assert client.get(f"/tasks/{task['id']}", headers=bob_headers).status_code == 404
    assert client.put(f"/tasks/{task['id']}", json={"status": "done"}, headers=bob_headers).status_code == 404


def test_init_db_migrates_existing_tasks_without_data_loss(tmp_path, monkeypatch):
    data_file = tmp_path / "tasks.json"
    legacy_task = {"id": 1, "title": "Legacy", "status": "pending", "created_at": "2020-01-01T00:00:00+00:00"}
    data_file.write_text(json.dumps({"next_id": 2, "tasks": [legacy_task]}), encoding="utf-8")
    monkeypatch.setattr(task_app, "DATABASE", str(data_file))

    task_app.init_db()

    store = json.loads(data_file.read_text(encoding="utf-8"))
    assert store["tasks"][0]["title"] == "Legacy"
    assert store["tasks"][0]["owner_id"] is None
    assert store["users"] == []
    assert store["next_user_id"] == 1
