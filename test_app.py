import json

import pytest

from app import app


@pytest.fixture
def client(tmp_path):
    app.config.update(TESTING=True, DATA_FILE=str(tmp_path / "tasks.json"))
    return app.test_client()


def test_create_and_get_task(client):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    assert response.get_json()["status"] == "pending"
    task_id = response.get_json()["id"]
    assert client.get(f"/tasks/{task_id}").get_json()["title"] == "Write tests"


def test_create_requires_title(client):
    assert client.post("/tasks", json={}).status_code == 400
    assert client.post("/tasks", json={"title": "  "}).get_json() == {
        "error": "title is required"
    }


def test_list_is_newest_first(client):
    first = client.post("/tasks", json={"title": "First"}).get_json()
    second = client.post("/tasks", json={"title": "Second"}).get_json()

    tasks = client.get("/tasks").get_json()
    assert [task["id"] for task in tasks] == [second["id"], first["id"]]


def test_update_title_and_status(client):
    task = client.post("/tasks", json={"title": "Old"}).get_json()

    response = client.put(
        f"/tasks/{task['id']}", json={"title": "New", "status": "done"}
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "New"
    assert response.get_json()["status"] == "done"


def test_missing_tasks_return_json_404(client):
    assert client.get("/tasks/999").get_json() == {"error": "task not found"}
    response = client.put("/tasks/999", json={"status": "done"})
    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_tasks_are_persisted_as_json(client):
    client.post("/tasks", json={"title": "Persist me"})

    with open(app.config["DATA_FILE"], encoding="utf-8") as store:
        tasks = json.load(store)

    assert tasks[0]["title"] == "Persist me"


def test_update_rejects_invalid_fields(client):
    task = client.post("/tasks", json={"title": "Valid"}).get_json()

    assert client.put(f"/tasks/{task['id']}", json={"title": ""}).status_code == 400
    assert client.put(f"/tasks/{task['id']}", json={"status": 1}).status_code == 400
