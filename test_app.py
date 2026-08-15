import json

import app as task_app
import pytest
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.json"))
    # The application uses Redis in production; isolate tests from external services.
    storage = MemoryStorage()
    monkeypatch.setattr(task_app.limiter, "_storage", storage)
    monkeypatch.setattr(task_app.limiter, "_limiter", FixedWindowRateLimiter(storage))
    monkeypatch.setattr(task_app.limiter, "_storage_dead", False)
    task_app.init_db()
    task_app.app.config.update(TESTING=True)
    return task_app.app.test_client()


def auth_headers(client, username="alice", password="secret", email=None):
    registration_data = {"username": username, "password": password}
    if email is not None:
        registration_data["email"] = email
    assert client.post("/auth/register", json=registration_data).status_code == 201
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
    assert [task["title"] for task in response.json["data"]] == ["Second", "First"]
    assert response.json["next_cursor"] is None
    assert response.json["total"] == 2


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


def test_completing_task_enqueues_notification(client, monkeypatch):
    headers = auth_headers(client, "owner", email="owner@example.com")
    task = client.post("/tasks", json={"title": "Notify me"}, headers=headers).json
    delay_calls = []
    monkeypatch.setattr(task_app.send_notification_email, "delay", lambda *args: delay_calls.append(args))

    response = client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)

    assert response.status_code == 200
    assert delay_calls == [("owner@example.com", "Notify me")]


def test_notification_is_not_enqueued_without_completion_transition(client, monkeypatch):
    headers = auth_headers(client, "owner", email="owner@example.com")
    task = client.post("/tasks", json={"title": "No duplicate"}, headers=headers).json
    delay_calls = []
    monkeypatch.setattr(task_app.send_notification_email, "delay", lambda *args: delay_calls.append(args))

    client.put(f"/tasks/{task['id']}", json={"status": "done"}, headers=headers)
    client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)
    client.put(f"/tasks/{task['id']}", json={"status": "completed"}, headers=headers)

    assert delay_calls == [("owner@example.com", "No duplicate")]


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

    assert client.get("/tasks", headers=bob_headers).json == {"data": [], "next_cursor": None, "total": 0}
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


def test_list_tasks_uses_cursor_pagination(client):
    headers = auth_headers(client)
    for title in ["First", "Second", "Third"]:
        assert client.post("/tasks", json={"title": title}, headers=headers).status_code == 201

    first_page = client.get("/tasks?limit=2", headers=headers)

    assert first_page.status_code == 200
    assert [task["title"] for task in first_page.json["data"]] == ["Third", "Second"]
    assert first_page.json["next_cursor"] == "2"
    assert first_page.json["total"] == 3

    second_page = client.get(f"/tasks?cursor={first_page.json['next_cursor']}&limit=2", headers=headers)

    assert [task["title"] for task in second_page.json["data"]] == ["First"]
    assert second_page.json["next_cursor"] is None
    assert second_page.json["total"] == 3


def test_list_tasks_rejects_invalid_pagination_parameters(client):
    headers = auth_headers(client)

    assert client.get("/tasks?limit=101", headers=headers).status_code == 400
    assert client.get("/tasks?cursor=not-an-id", headers=headers).status_code == 400


def test_rate_limit_applies_to_authenticated_users_and_returns_retry_after(client):
    headers = auth_headers(client)

    for _ in range(100):
        assert client.get("/tasks", headers=headers).status_code == 200
    response = client.get("/tasks", headers=headers)

    assert response.status_code == 429
    assert response.json == {"error": "rate limit exceeded"}
    assert response.headers["Retry-After"]


def test_rate_limit_also_applies_to_auth_endpoints(client):
    for _ in range(100):
        assert client.post("/auth/register", json={}).status_code == 400

    response = client.post("/auth/register", json={})

    assert response.status_code == 429
    assert response.headers["Retry-After"]
