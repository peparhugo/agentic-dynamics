import os

import pytest

import app as task_app


@pytest.fixture
def client(tmp_path):
    original_database = task_app.DATABASE
    task_app.DATABASE = os.fspath(tmp_path / "test.db")
    task_app.init_db()
    task_app.app.config["TESTING"] = True
    with task_app.app.test_client() as test_client:
        yield test_client
    task_app.DATABASE = original_database


def test_create_task_uses_pending_status(client):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    assert response.json["title"] == "Write tests"
    assert response.json["status"] == "pending"
    assert response.json["id"] == 1
    assert response.json["created_at"]


def test_create_task_requires_title(client):
    response = client.post("/tasks", json={})

    assert response.status_code == 400
    assert response.json == {"error": "title is required"}


def test_list_tasks_is_newest_first(client):
    client.post("/tasks", json={"title": "First"})
    client.post("/tasks", json={"title": "Second"})

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["title"] for task in response.json] == ["Second", "First"]


def test_get_task_and_missing_task(client):
    created = client.post("/tasks", json={"title": "Find me"}).json

    assert client.get(f"/tasks/{created['id']}").json == created
    missing = client.get("/tasks/999")
    assert missing.status_code == 404
    assert missing.json == {"error": "task not found"}


def test_update_task_title_and_status(client):
    created = client.post("/tasks", json={"title": "Old"}).json

    response = client.put(
        f"/tasks/{created['id']}",
        json={"title": "New", "status": "done"},
    )

    assert response.status_code == 200
    assert response.json["title"] == "New"
    assert response.json["status"] == "done"
    assert response.json["created_at"] == created["created_at"]


def test_update_task_requires_a_supported_field(client):
    response = client.put("/tasks/999", json={})

    assert response.status_code == 400
    assert response.json == {"error": "title or status is required"}


def test_update_missing_task_returns_not_found(client):
    response = client.put("/tasks/999", json={"status": "done"})

    assert response.status_code == 404
    assert response.json == {"error": "task not found"}
