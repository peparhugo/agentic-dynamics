import json

import app as task_app
import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.json"))
    task_app.init_db()
    task_app.app.config.update(TESTING=True)
    return task_app.app.test_client()


def test_create_task_and_default_fields(client):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    assert response.json["id"] == 1
    assert response.json["title"] == "Write tests"
    assert response.json["status"] == "pending"
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


def test_get_and_update_task(client):
    task = client.post("/tasks", json={"title": "Original"}).json

    response = client.put(
        f"/tasks/{task['id']}", json={"title": "Updated", "status": "done"}
    )

    assert response.status_code == 200
    assert response.json["title"] == "Updated"
    assert response.json["status"] == "done"
    assert client.get(f"/tasks/{task['id']}").json == response.json


def test_missing_task_returns_json_not_found_error(client):
    response = client.get("/tasks/99")

    assert response.status_code == 404
    assert response.json == {"error": "task not found"}


def test_tasks_are_written_to_a_flat_file(client, tmp_path, monkeypatch):
    data_file = tmp_path / "persisted-tasks.json"
    monkeypatch.setattr(task_app, "DATABASE", str(data_file))
    task_app.init_db()

    client.post("/tasks", json={"title": "Persist me"})

    assert json.loads(data_file.read_text(encoding="utf-8"))["tasks"][0]["title"] == "Persist me"
