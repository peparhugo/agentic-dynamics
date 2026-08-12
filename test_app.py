import pytest

import app as task_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    return task_app.app.test_client()


def test_create_task_defaults_to_pending(client):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    assert response.json["title"] == "Write tests"
    assert response.json["status"] == "pending"
    assert response.json["id"] == 1


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": 42}])
def test_create_task_requires_title(client, body):
    response = client.post("/tasks", json=body)

    assert response.status_code == 400
    assert "error" in response.json


def test_list_tasks_is_newest_first(client):
    client.post("/tasks", json={"title": "First"})
    client.post("/tasks", json={"title": "Second"})

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["title"] for task in response.json] == ["Second", "First"]


def test_get_task_and_missing_task(client):
    created = client.post("/tasks", json={"title": "Read"}).json

    assert client.get(f"/tasks/{created['id']}").json == created
    missing = client.get("/tasks/999")
    assert missing.status_code == 404
    assert missing.json == {"error": "task not found"}


def test_update_task_fields(client):
    created = client.post("/tasks", json={"title": "Old"}).json

    response = client.put(
        f"/tasks/{created['id']}", json={"title": "New", "status": "done"}
    )

    assert response.status_code == 200
    assert response.json["title"] == "New"
    assert response.json["status"] == "done"


def test_update_missing_task_returns_not_found(client):
    response = client.put("/tasks/999", json={"status": "done"})

    assert response.status_code == 404
    assert response.json == {"error": "task not found"}
