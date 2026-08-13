import pytest

import app as task_app


@pytest.fixture()
def client(tmp_path):
    application = task_app.create_app(
        {"TESTING": True, "DATABASE": str(tmp_path / "tasks.db")}
    )
    return application.test_client()


def test_create_and_get_task(client):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    task = response.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]

    assert client.get("/tasks/1").get_json() == task


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "   "}])
def test_create_requires_title(client, body):
    response = client.post("/tasks", json=body)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_newest_first(client):
    first = client.post("/tasks", json={"title": "First"}).get_json()
    second = client.post("/tasks", json={"title": "Second"}).get_json()

    response = client.get("/tasks")

    assert response.status_code == 200
    assert response.get_json() == [second, first]


def test_update_title_and_status(client):
    task_id = client.post("/tasks", json={"title": "Draft"}).get_json()["id"]

    response = client.put(
        f"/tasks/{task_id}", json={"title": "Final", "status": "completed"}
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "Final"
    assert response.get_json()["status"] == "completed"


def test_update_single_field(client):
    task_id = client.post("/tasks", json={"title": "Task"}).get_json()["id"]

    response = client.put(f"/tasks/{task_id}", json={"status": "in-progress"})

    assert response.status_code == 200
    assert response.get_json()["title"] == "Task"
    assert response.get_json()["status"] == "in-progress"


@pytest.mark.parametrize("method", ["get", "put"])
def test_missing_task_returns_404(client, method):
    if method == "get":
        response = client.get("/tasks/999")
    else:
        response = client.put("/tasks/999", json={"status": "completed"})

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_update_requires_supported_field(client):
    task_id = client.post("/tasks", json={"title": "Task"}).get_json()["id"]

    response = client.put(f"/tasks/{task_id}", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "title or status is required"}
