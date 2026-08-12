import app as task_app
import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    with task_app.app.test_client() as test_client:
        yield test_client


def test_create_and_get_task(client):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    task = response.get_json()
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]

    fetched = client.get(f"/tasks/{task['id']}")
    assert fetched.status_code == 200
    assert fetched.get_json() == task


def test_list_tasks_is_ordered_newest_first(client):
    first = client.post("/tasks", json={"title": "First"}).get_json()
    second = client.post("/tasks", json={"title": "Second"}).get_json()

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["id"] for task in response.get_json()] == [second["id"], first["id"]]


def test_create_requires_title(client):
    response = client.post("/tasks", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_update_task_fields(client):
    task = client.post("/tasks", json={"title": "Old"}).get_json()

    response = client.put(f"/tasks/{task['id']}", json={"title": "New", "status": "done"})

    assert response.status_code == 200
    assert response.get_json()["title"] == "New"
    assert response.get_json()["status"] == "done"


def test_missing_task_returns_json_404(client):
    assert client.get("/tasks/999").get_json() == {"error": "task not found"}
    assert client.get("/tasks/999").status_code == 404
    assert client.put("/tasks/999", json={"status": "done"}).get_json() == {
        "error": "task not found"
    }


def test_put_requires_an_update_field(client):
    task = client.post("/tasks", json={"title": "Unchanged"}).get_json()

    response = client.put(f"/tasks/{task['id']}", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "title or status is required"}
