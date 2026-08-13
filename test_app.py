import json

import app
import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "DATA_FILE", str(tmp_path / "tasks.json"))
    monkeypatch.setattr(app, "JWT_SECRET", "test-secret")
    app.init_db()
    return app.app.test_client()


def register(client, username="alice", password="correct horse battery staple"):
    return client.post("/auth/register", json={"username": username, "password": password})


def auth_headers(client, username="alice", password="correct horse battery staple"):
    register(client, username, password)
    response = client.post("/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def test_register_creates_user_with_hashed_password(client, tmp_path):
    response = register(client)

    assert response.status_code == 201
    assert response.get_json() == {"id": 1, "username": "alice"}
    user = json.loads((tmp_path / "users.json").read_text())[0]
    assert user["password_hash"] != "correct horse battery staple"


def test_register_rejects_duplicate_username(client):
    register(client)

    response = register(client)

    assert response.status_code == 409
    assert response.get_json() == {"error": "username already exists"}


def test_login_returns_token_and_rejects_bad_password(client):
    register(client)

    success = client.post("/auth/login", json={"username": "alice", "password": "correct horse battery staple"})
    failure = client.post("/auth/login", json={"username": "alice", "password": "wrong"})

    assert isinstance(success.get_json()["token"], str)
    assert failure.status_code == 401
    assert failure.get_json() == {"error": "invalid username or password"}


@pytest.mark.parametrize("method,path", [("get", "/tasks"), ("post", "/tasks"), ("get", "/tasks/1"), ("put", "/tasks/1")])
def test_task_endpoints_require_authentication(client, method, path):
    response = getattr(client, method)(path, json={"title": "Write tests"})

    assert response.status_code == 401
    assert response.get_json() == {"error": "authentication required"}


def test_create_task_uses_pending_status(client):
    headers = auth_headers(client)
    response = client.post("/tasks", json={"title": "Write tests"}, headers=headers)

    assert response.status_code == 201
    task = response.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["owner_id"] == 1
    assert task["created_at"]


@pytest.mark.parametrize("payload", ({}, {"title": ""}, {"title": 3}))
def test_create_task_requires_a_title(client, payload):
    response = client.post("/tasks", json=payload, headers=auth_headers(client))

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_orders_newest_first(client):
    headers = auth_headers(client)
    client.post("/tasks", json={"title": "First"}, headers=headers)
    client.post("/tasks", json={"title": "Second"}, headers=headers)

    response = client.get("/tasks", headers=headers)

    assert response.status_code == 200
    assert [task["title"] for task in response.get_json()] == ["Second", "First"]


def test_users_can_only_access_their_own_tasks(client):
    alice_headers = auth_headers(client, "alice")
    bob_headers = auth_headers(client, "bob")
    task = client.post("/tasks", json={"title": "Alice private task"}, headers=alice_headers).get_json()

    assert client.get("/tasks", headers=bob_headers).get_json() == []
    assert client.get(f"/tasks/{task['id']}", headers=bob_headers).status_code == 404
    assert client.put(f"/tasks/{task['id']}", json={"status": "done"}, headers=bob_headers).status_code == 404


def test_get_and_update_task(client):
    headers = auth_headers(client)
    created = client.post("/tasks", json={"title": "Draft"}, headers=headers).get_json()

    response = client.put(
        f"/tasks/{created['id']}", json={"title": "Published", "status": "done"}, headers=headers
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "Published"
    assert response.get_json()["status"] == "done"
    assert client.get(f"/tasks/{created['id']}", headers=headers).get_json() == response.get_json()


def test_completing_task_queues_owner_notification(client, monkeypatch):
    headers = auth_headers(client)
    created = client.post("/tasks", json={"title": "Notify me"}, headers=headers).get_json()
    calls = []
    monkeypatch.setattr(app.send_notification_email, "delay", lambda *args: calls.append(args))

    response = client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers)

    assert response.status_code == 200
    assert calls == [("alice", "Notify me")]


def test_recompleting_task_does_not_queue_duplicate_notification(client, monkeypatch):
    headers = auth_headers(client)
    created = client.post("/tasks", json={"title": "Only once"}, headers=headers).get_json()
    calls = []
    monkeypatch.setattr(app.send_notification_email, "delay", lambda *args: calls.append(args))

    client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers)
    response = client.put(f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers)

    assert response.status_code == 200
    assert calls == [("alice", "Only once")]


def test_missing_task_returns_json_404(client):
    response = client.get("/tasks/99", headers=auth_headers(client))

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_existing_tasks_are_migrated_without_data_loss(tmp_path, monkeypatch):
    tasks_file = tmp_path / "tasks.json"
    tasks_file.write_text('[{"id": 1, "title": "Legacy", "status": "pending", "created_at": "2025-01-01T00:00:00+00:00"}]')
    monkeypatch.setattr(app, "DATA_FILE", str(tasks_file))

    app.init_db()

    assert json.loads(tasks_file.read_text())[0]["owner_id"] is None


def test_tasks_are_persisted_to_flat_file(client, tmp_path):
    headers = auth_headers(client)
    client.post("/tasks", json={"title": "Persisted"}, headers=headers)

    persisted = json.loads((tmp_path / "tasks.json").read_text())[0]
    assert persisted == {
        "id": 1,
        "title": "Persisted",
        "status": "pending",
        "created_at": persisted["created_at"],
        "owner_id": 1,
    }
