import json
from unittest.mock import patch

import pytest

from app import app, init_storage


@pytest.fixture()
def client(tmp_path):
    app.config.update(TESTING=True, TASKS_FILE=str(tmp_path / "tasks.json"), JWT_SECRET="test-secret")
    init_storage()
    with app.test_client() as test_client:
        yield test_client


def register_and_login(client, username="alice", password="secret"):
    assert client.post("/auth/register", json={"username": username, "password": password}).status_code == 201
    response = client.post("/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def test_registration_hashes_password_and_login_returns_token(client):
    headers = register_and_login(client)
    assert headers["Authorization"].startswith("Bearer ")
    with open(app.config["TASKS_FILE"], encoding="utf-8") as data_file:
        user = json.load(data_file)["users"][0]
    assert user["username"] == "alice"
    assert user["password_hash"] != "secret"


@pytest.mark.parametrize("payload", [{}, {"username": "alice"}, {"password": "secret"}, None])
def test_register_requires_username_and_password(client, payload):
    assert client.post("/auth/register", json=payload).status_code == 400


def test_register_rejects_duplicate_and_login_rejects_bad_credentials(client):
    register_and_login(client)
    assert client.post("/auth/register", json={"username": "alice", "password": "other"}).status_code == 409
    assert client.post("/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401


def test_tasks_require_a_valid_token(client):
    assert client.get("/tasks").status_code == 401
    assert client.post("/tasks", json={"title": "Nope"}).status_code == 401
    assert client.get("/tasks", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_create_task_uses_defaults_and_persists(client):
    headers = register_and_login(client)
    response = client.post("/tasks", json={"title": "Write docs"}, headers=headers)

    assert response.status_code == 201
    task = response.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write docs"
    assert task["status"] == "pending"
    assert task["created_at"]
    assert task["owner_id"] == 1

    with open(app.config["TASKS_FILE"], encoding="utf-8") as tasks_file:
        assert json.load(tasks_file)["tasks"] == [task]


@pytest.mark.parametrize("payload", [{}, {"title": ""}, {"title": 2}, None])
def test_create_task_requires_a_title(client, payload):
    headers = register_and_login(client)
    response = client.post("/tasks", json=payload, headers=headers)
    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_is_newest_first_and_isolated_by_owner(client):
    alice = register_and_login(client)
    first = client.post("/tasks", json={"title": "First"}, headers=alice).get_json()
    second = client.post("/tasks", json={"title": "Second"}, headers=alice).get_json()
    bob = register_and_login(client, "bob")

    assert [task["id"] for task in client.get("/tasks", headers=alice).get_json()] == [second["id"], first["id"]]
    assert client.get("/tasks", headers=bob).get_json() == []
    assert client.get(f"/tasks/{first['id']}", headers=bob).status_code == 404
    assert client.put(f"/tasks/{first['id']}", json={"status": "done"}, headers=bob).status_code == 404


def test_get_and_update_owned_task(client):
    headers = register_and_login(client)
    task = client.post("/tasks", json={"title": "Draft"}, headers=headers).get_json()
    assert client.get(f"/tasks/{task['id']}", headers=headers).get_json() == task

    response = client.put(f"/tasks/{task['id']}", json={"title": "Published", "status": "done"}, headers=headers)
    assert response.status_code == 200
    assert response.get_json() == {**task, "title": "Published", "status": "done"}


def test_completing_task_enqueues_notification_once(client):
    assert client.post(
        "/auth/register", json={"username": "alice", "password": "secret", "email": "alice@example.com"}
    ).status_code == 201
    login = client.post("/auth/login", json={"username": "alice", "password": "secret"})
    headers = {"Authorization": f"Bearer {login.get_json()['token']}"}
    task = client.post("/tasks", json={"title": "Ship release"}, headers=headers).get_json()

    with patch("app.send_notification_email.delay") as delay:
        response = client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)
        assert response.status_code == 200
        delay.assert_called_once_with("alice@example.com", "Ship release")

        client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)
        delay.assert_called_once()


def test_update_task_validates_input_and_missing_task(client):
    headers = register_and_login(client)
    task = client.post("/tasks", json={"title": "Draft"}, headers=headers).get_json()
    assert client.put(f"/tasks/{task['id']}", json={}, headers=headers).status_code == 400
    assert client.put(f"/tasks/{task['id']}", json={"title": ""}, headers=headers).status_code == 400
    assert client.put(f"/tasks/{task['id']}", json={"status": 1}, headers=headers).status_code == 400
    missing = client.put("/tasks/99", json={"status": "done"}, headers=headers)
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "task not found"}


def test_init_storage_migrates_legacy_tasks_without_data_loss(tmp_path):
    path = tmp_path / "tasks.json"
    legacy_task = {"id": 4, "title": "Existing", "status": "pending", "created_at": "2020-01-01T00:00:00+00:00"}
    path.write_text(json.dumps([legacy_task]), encoding="utf-8")
    app.config["TASKS_FILE"] = str(path)
    init_storage()
    assert json.loads(path.read_text(encoding="utf-8")) == {"users": [], "tasks": [{**legacy_task, "owner_id": None}]}
