import app as task_app
import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "test.db"))
    task_app.init_db()
    task_app.app.config.update(TESTING=True)
    return task_app.app.test_client()


def test_create_and_get_task(client):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    task = response.get_json()
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]

    response = client.get(f"/tasks/{task['id']}")
    assert response.status_code == 200
    assert response.get_json() == task


def test_list_tasks_newest_first(client):
    first = client.post("/tasks", json={"title": "First"}).get_json()
    second = client.post("/tasks", json={"title": "Second"}).get_json()

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["id"] for task in response.get_json()] == [second["id"], first["id"]]


def test_update_task(client):
    task_id = client.post("/tasks", json={"title": "Old"}).get_json()["id"]

    response = client.put(
        f"/tasks/{task_id}", json={"title": "New", "status": "completed"}
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "New"
    assert response.get_json()["status"] == "completed"


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "   "}, {"title": 1}])
def test_create_requires_title(client, body):
    response = client.post("/tasks", json=body)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_missing_tasks_return_404(client):
    assert client.get("/tasks/999").status_code == 404
    assert client.put("/tasks/999", json={"status": "done"}).status_code == 404
    assert client.get("/tasks/999").get_json() == {"error": "task not found"}


def test_update_requires_valid_fields(client):
    task_id = client.post("/tasks", json={"title": "Task"}).get_json()["id"]

    assert client.put(f"/tasks/{task_id}", json={}).status_code == 400
    assert client.put(f"/tasks/{task_id}", json={"title": ""}).status_code == 400
    assert client.put(f"/tasks/{task_id}", json={"status": None}).status_code == 400
