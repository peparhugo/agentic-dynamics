import json
from datetime import datetime

import pytest

from app import create_app


@pytest.fixture
def data_file(tmp_path):
    return tmp_path / "tasks.json"


@pytest.fixture
def client(data_file):
    app = create_app({"TESTING": True, "TASKS_FILE": str(data_file)})
    return app.test_client()


def test_storage_is_initialized(data_file):
    create_app({"TESTING": True, "TASKS_FILE": str(data_file)})
    assert json.loads(data_file.read_text()) == []


def test_create_task(client):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    assert response.json["id"] == 1
    assert response.json["title"] == "Write tests"
    assert response.json["status"] == "pending"
    datetime.fromisoformat(response.json["created_at"])


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "   "}, None])
def test_create_requires_title(client, body):
    response = client.post("/tasks", json=body)

    assert response.status_code == 400
    assert response.json == {"error": "title is required"}


def test_list_tasks_newest_first(client):
    first = client.post("/tasks", json={"title": "First"}).json
    second = client.post("/tasks", json={"title": "Second"}).json

    response = client.get("/tasks")

    assert response.status_code == 200
    assert response.json == [second, first]


def test_get_task_and_missing_task(client):
    task = client.post("/tasks", json={"title": "Existing"}).json

    assert client.get(f"/tasks/{task['id']}").json == task
    missing = client.get("/tasks/999")
    assert missing.status_code == 404
    assert missing.json == {"error": "task not found"}


def test_update_title_and_status(client):
    task = client.post("/tasks", json={"title": "Old title"}).json

    response = client.put(
        f"/tasks/{task['id']}", json={"title": "New title", "status": "done"}
    )

    assert response.status_code == 200
    assert response.json["title"] == "New title"
    assert response.json["status"] == "done"
    assert response.json["created_at"] == task["created_at"]


def test_update_one_field(client):
    task = client.post("/tasks", json={"title": "Task"}).json

    response = client.put(f"/tasks/{task['id']}", json={"status": "active"})

    assert response.json["title"] == "Task"
    assert response.json["status"] == "active"


def test_update_validates_body_and_missing_task(client):
    task = client.post("/tasks", json={"title": "Task"}).json

    invalid = client.put(f"/tasks/{task['id']}", json={"title": " "})
    assert invalid.status_code == 400
    assert "error" in invalid.json

    missing = client.put("/tasks/999", json={"status": "done"})
    assert missing.status_code == 404
    assert missing.json == {"error": "task not found"}


def test_tasks_persist_between_app_instances(data_file):
    first_client = create_app(
        {"TESTING": True, "TASKS_FILE": str(data_file)}
    ).test_client()
    created = first_client.post("/tasks", json={"title": "Persistent"}).json

    second_client = create_app(
        {"TESTING": True, "TASKS_FILE": str(data_file)}
    ).test_client()
    assert second_client.get("/tasks").json == [created]
