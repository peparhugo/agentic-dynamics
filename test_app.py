import sqlite3

import pytest

import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(app, "DATABASE", str(database))
    app.init_db()
    with app.app.test_client() as client:
        yield client


def test_create_task_uses_pending_status(client):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    assert response.json["id"] == 1
    assert response.json["title"] == "Write tests"
    assert response.json["status"] == "pending"
    assert response.json["created_at"]


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": 5}])
def test_create_task_requires_title(client, body):
    response = client.post("/tasks", json=body)

    assert response.status_code == 400
    assert response.json == {"error": "title is required"}


def test_list_tasks_returns_newest_first(client):
    first = client.post("/tasks", json={"title": "First"}).json
    second = client.post("/tasks", json={"title": "Second"}).json

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["id"] for task in response.json] == [second["id"], first["id"]]


def test_get_task_and_missing_task(client):
    task = client.post("/tasks", json={"title": "Fetch me"}).json

    response = client.get(f"/tasks/{task['id']}")
    missing_response = client.get("/tasks/99")

    assert response.status_code == 200
    assert response.json == task
    assert missing_response.status_code == 404
    assert missing_response.json == {"error": "task not found"}


def test_update_task_title_and_status(client):
    task = client.post("/tasks", json={"title": "Original"}).json

    response = client.put(
        f"/tasks/{task['id']}", json={"title": "Updated", "status": "done"}
    )

    assert response.status_code == 200
    assert response.json == {**task, "title": "Updated", "status": "done"}


def test_update_missing_task_returns_json_404(client):
    response = client.put("/tasks/99", json={"status": "done"})

    assert response.status_code == 404
    assert response.json == {"error": "task not found"}
