import json

import pytest

import app as task_app
from celery_config import celery_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    data_file = tmp_path / "tasks.json"
    monkeypatch.setattr(task_app, "DATA_FILE", data_file)
    task_app.limiter.reset()
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
    response = auth_client.get("/tasks")
    assert [task["title"] for task in response.json["data"]] == ["Second", "First"]
    assert response.json["next_cursor"] is None
    assert response.json["total"] == 2


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


def test_completing_task_queues_notification(auth_client, monkeypatch):
    created = auth_client.post("/tasks", json={"title": "Ship it"}).json
    queued = []

    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda email, title: queued.append((email, title)),
    )

    response = auth_client.put(f"/tasks/{created['id']}", json={"status": "completed"})

    assert response.status_code == 200
    assert queued == [("alice", "Ship it")]


def test_notification_is_only_queued_on_transition_to_completed(auth_client, monkeypatch):
    created = auth_client.post("/tasks", json={"title": "Ship it"}).json
    queued = []
    monkeypatch.setattr(task_app.send_notification_email, "delay", lambda *args: queued.append(args))

    auth_client.put(f"/tasks/{created['id']}", json={"title": "Renamed"})
    auth_client.put(f"/tasks/{created['id']}", json={"status": "completed"})
    auth_client.put(f"/tasks/{created['id']}", json={"status": "completed"})

    assert queued == [("alice", "Renamed")]


def test_celery_uses_redis_and_notification_route():
    assert celery_app.conf.broker_url == "redis://localhost:6379/0"
    assert celery_app.conf.result_backend == "redis://localhost:6379/0"
    assert celery_app.conf.task_routes["notifications.send_notification_email"]["queue"] == "notifications"


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
    assert client.get("/tasks").json == {"data": [], "next_cursor": None, "total": 0}
    assert client.get(f"/tasks/{task['id']}").status_code == 404


def test_register_login_and_duplicate_username(client):
    response = client.post("/auth/register", json={"username": "alice", "password": "secret"})
    assert response.status_code == 201
    assert "password_hash" not in response.json
    assert client.post("/auth/register", json={"username": "alice", "password": "other"}).status_code == 409
    assert client.post("/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401
    assert "token" in client.post("/auth/login", json={"username": "alice", "password": "secret"}).json


def test_tasks_are_cursor_paginated(auth_client):
    for title in ("First", "Second", "Third"):
        auth_client.post("/tasks", json={"title": title})

    first_page = auth_client.get("/tasks?limit=2")
    assert first_page.status_code == 200
    assert [task["title"] for task in first_page.json["data"]] == ["Third", "Second"]
    assert first_page.json["next_cursor"] == str(first_page.json["data"][-1]["id"])
    assert first_page.json["total"] == 3

    second_page = auth_client.get(f"/tasks?cursor={first_page.json['next_cursor']}&limit=2")
    assert [task["title"] for task in second_page.json["data"]] == ["First"]
    assert second_page.json == {
        "data": second_page.json["data"],
        "next_cursor": None,
        "total": 3,
    }


def test_pagination_validates_cursor_and_limit(auth_client):
    assert auth_client.get("/tasks?limit=0").status_code == 400
    assert auth_client.get("/tasks?limit=101").status_code == 400
    assert auth_client.get("/tasks?limit=invalid").status_code == 400
    assert auth_client.get("/tasks?cursor=invalid").status_code == 400
    assert auth_client.get("/tasks?cursor=999").status_code == 400


def test_rate_limit_returns_retry_after(client):
    task_app.limiter.reset()
    client.post("/auth/register", json={"username": "limited", "password": "secret"})
    for _ in range(100):
        response = client.post("/auth/login", json={"username": "limited", "password": "secret"})
        assert response.status_code == 200
    response = client.post("/auth/login", json={"username": "limited", "password": "secret"})
    assert response.status_code == 429
    assert response.headers["Retry-After"]
    assert response.json == {"error": "rate limit exceeded"}
