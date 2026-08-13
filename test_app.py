import sqlite3

import pytest

from app import app, init_db


@pytest.fixture()
def client(tmp_path):
    app.config.update(TESTING=True, DATABASE=str(tmp_path / "tasks.db"))
    init_db()
    return app.test_client()


def create(client, title):
    response = client.post("/tasks", json={"title": title})
    assert response.status_code == 201
    return response.get_json()


def test_create_task_defaults_to_pending(client):
    task = create(client, "Write tests")

    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]


@pytest.mark.parametrize("payload", [{}, {"title": ""}, {"title": 3}])
def test_create_requires_a_title(client, payload):
    response = client.post("/tasks", json=payload)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_is_newest_first(client):
    older = create(client, "Older")
    newer = create(client, "Newer")

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["id"] for task in response.get_json()] == [newer["id"], older["id"]]


def test_get_and_update_task(client):
    task = create(client, "Draft")

    update_response = client.put(
        f"/tasks/{task['id']}", json={"title": "Published", "status": "done"}
    )

    assert update_response.status_code == 200
    assert update_response.get_json()["title"] == "Published"
    assert update_response.get_json()["status"] == "done"
    assert client.get(f"/tasks/{task['id']}").get_json() == update_response.get_json()


def test_missing_task_returns_json_404(client):
    response = client.get("/tasks/999")

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_update_requires_at_least_one_supported_field(client):
    task = create(client, "Task")

    response = client.put(f"/tasks/{task['id']}", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "title or status is required"}
