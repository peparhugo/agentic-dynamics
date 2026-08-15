import json

import pytest

import app as task_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    data_file = tmp_path / "tasks.json"
    monkeypatch.setattr(task_app, "DATA_FILE", data_file)
    task_app.init_storage()
    return task_app.app.test_client()


def test_create_task_defaults_status_and_lists_newest_first(client):
    first = client.post("/tasks", json={"title": "First"})
    second = client.post("/tasks", json={"title": "Second"})

    assert first.status_code == 201
    assert first.json["status"] == "pending"
    assert [task["title"] for task in client.get("/tasks").json] == ["Second", "First"]


def test_create_requires_title(client):
    response = client.post("/tasks", json={})

    assert response.status_code == 400
    assert response.json == {"error": "title is required"}


def test_get_and_update_task(client):
    created = client.post("/tasks", json={"title": "Old title"}).json

    response = client.put(
        f"/tasks/{created['id']}",
        json={"title": "New title", "status": "complete"},
    )

    assert response.status_code == 200
    assert response.json["title"] == "New title"
    assert response.json["status"] == "complete"
    assert client.get(f"/tasks/{created['id']}").json == response.json


def test_missing_task_returns_json_404(client):
    response = client.get("/tasks/123")

    assert response.status_code == 404
    assert response.json == {"error": "task not found"}


def test_storage_is_a_json_flat_file(client, tmp_path, monkeypatch):
    client.post("/tasks", json={"title": "Persisted"})

    data_file = task_app.DATA_FILE
    assert data_file.suffix == ".json"
    assert json.loads(data_file.read_text())["tasks"][0]["title"] == "Persisted"
