import app as task_app

import pytest


@pytest.fixture()
def client(tmp_path):
    database = tmp_path / "tasks.sqlite"
    task_app.app.config.update(TESTING=True, DATABASE=str(database))
    task_app.init_db()
    return task_app.app.test_client()


def test_create_task_uses_defaults(client):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    task = response.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]


def test_create_task_requires_title(client):
    response = client.post("/tasks", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_is_newest_first(client):
    first = client.post("/tasks", json={"title": "First"}).get_json()
    second = client.post("/tasks", json={"title": "Second"}).get_json()

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["id"] for task in response.get_json()] == [second["id"], first["id"]]


def test_get_task_and_missing_task(client):
    task = client.post("/tasks", json={"title": "Read"}).get_json()

    assert client.get(f"/tasks/{task['id']}").get_json() == task
    missing = client.get("/tasks/999")
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "task not found"}


def test_update_task_title_and_status(client):
    task = client.post("/tasks", json={"title": "Draft"}).get_json()

    response = client.put(
        f"/tasks/{task['id']}", json={"title": "Published", "status": "done"}
    )

    assert response.status_code == 200
    assert response.get_json() == {
        **task,
        "title": "Published",
        "status": "done",
    }


def test_update_missing_task_returns_json_404(client):
    response = client.put("/tasks/999", json={"status": "done"})

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}
