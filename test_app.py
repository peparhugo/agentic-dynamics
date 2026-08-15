import json

import pytest

from app import app, init_storage


@pytest.fixture()
def client(tmp_path):
    app.config.update(TESTING=True, TASKS_FILE=str(tmp_path / "tasks.json"))
    init_storage()
    with app.test_client() as test_client:
        yield test_client


def test_create_task_uses_defaults_and_persists(client):
    response = client.post("/tasks", json={"title": "Write docs"})

    assert response.status_code == 201
    task = response.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write docs"
    assert task["status"] == "pending"
    assert task["created_at"]

    with open(app.config["TASKS_FILE"], encoding="utf-8") as tasks_file:
        assert json.load(tasks_file) == [task]


@pytest.mark.parametrize("payload", [{}, {"title": ""}, {"title": 2}, None])
def test_create_task_requires_a_title(client, payload):
    response = client.post("/tasks", json=payload)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_is_newest_first(client):
    first = client.post("/tasks", json={"title": "First"}).get_json()
    second = client.post("/tasks", json={"title": "Second"}).get_json()

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["id"] for task in response.get_json()] == [second["id"], first["id"]]


def test_get_task_and_missing_task(client):
    task = client.post("/tasks", json={"title": "Find me"}).get_json()

    assert client.get(f"/tasks/{task['id']}").get_json() == task
    missing = client.get("/tasks/99")
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "task not found"}


def test_update_task_title_and_status(client):
    task = client.post("/tasks", json={"title": "Draft"}).get_json()

    response = client.put(
        f"/tasks/{task['id']}", json={"title": "Published", "status": "done"}
    )

    assert response.status_code == 200
    assert response.get_json() == {**task, "title": "Published", "status": "done"}


def test_update_task_validates_input_and_missing_task(client):
    task = client.post("/tasks", json={"title": "Draft"}).get_json()

    assert client.put(f"/tasks/{task['id']}", json={}).status_code == 400
    assert client.put(f"/tasks/{task['id']}", json={"title": ""}).status_code == 400
    assert client.put(f"/tasks/{task['id']}", json={"status": 1}).status_code == 400
    missing = client.put("/tasks/99", json={"status": "done"})
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "task not found"}
