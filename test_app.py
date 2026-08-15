import pytest

from app import app, init_db


@pytest.fixture()
def client(tmp_path):
    app.config.update(TESTING=True, TASKS_FILE=str(tmp_path / "tasks.json"))
    init_db()
    with app.test_client() as test_client:
        yield test_client


def test_create_and_list_tasks(client):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    task = response.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert client.get("/tasks").get_json() == [task]


def test_create_requires_title(client):
    response = client.post("/tasks", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_get_update_and_missing_task(client):
    client.post("/tasks", json={"title": "Old title"})

    response = client.put("/tasks/1", json={"title": "New title", "status": "done"})
    assert response.status_code == 200
    assert response.get_json()["title"] == "New title"
    assert response.get_json()["status"] == "done"
    assert client.get("/tasks/1").get_json()["title"] == "New title"

    missing = client.get("/tasks/99")
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "task not found"}
