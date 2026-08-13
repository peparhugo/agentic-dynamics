import pytest

import app as task_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    task_app.app.config.update(TESTING=True)
    return task_app.app.test_client()


def test_create_task(client):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    assert response.get_json()["title"] == "Write tests"
    assert response.get_json()["status"] == "pending"
    assert response.get_json()["created_at"]


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "   "}, {"title": 1}])
def test_create_requires_title(client, body):
    response = client.post("/tasks", json=body)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_newest_first(client):
    first = client.post("/tasks", json={"title": "First"}).get_json()
    second = client.post("/tasks", json={"title": "Second"}).get_json()

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["id"] for task in response.get_json()] == [second["id"], first["id"]]


def test_get_task(client):
    created = client.post("/tasks", json={"title": "Read me"}).get_json()

    response = client.get(f"/tasks/{created['id']}")

    assert response.status_code == 200
    assert response.get_json() == created


def test_missing_task_returns_json_404(client):
    response = client.get("/tasks/999")

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_update_task(client):
    created = client.post("/tasks", json={"title": "Old title"}).get_json()

    response = client.put(
        f"/tasks/{created['id']}",
        json={"title": "New title", "status": "completed"},
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "New title"
    assert response.get_json()["status"] == "completed"
    assert response.get_json()["created_at"] == created["created_at"]


def test_update_single_field(client):
    created = client.post("/tasks", json={"title": "Task"}).get_json()

    response = client.put(f"/tasks/{created['id']}", json={"status": "active"})

    assert response.status_code == 200
    assert response.get_json()["title"] == "Task"
    assert response.get_json()["status"] == "active"


def test_update_missing_task_returns_404(client):
    response = client.put("/tasks/999", json={"status": "completed"})

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_invalid_update_returns_400(client):
    created = client.post("/tasks", json={"title": "Task"}).get_json()

    response = client.put(f"/tasks/{created['id']}", json={"title": ""})

    assert response.status_code == 400
    assert response.get_json() == {"error": "title must be a non-empty string"}
