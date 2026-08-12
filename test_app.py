import os
import tempfile

import pytest

import app as app_module


@pytest.fixture
def client():
    fd, path = tempfile.mkstemp()
    app_module.DATABASE = path
    app_module.app.config["TESTING"] = True
    app_module.init_db()

    with app_module.app.test_client() as client:
        yield client

    os.close(fd)
    os.unlink(path)


def test_post_missing_title_returns_400(client):
    response = client.post("/tasks", json={})
    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_post_blank_title_returns_400(client):
    response = client.post("/tasks", json={"title": "   "})
    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_post_no_body_returns_400(client):
    response = client.post("/tasks")
    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_post_creates_task(client):
    response = client.post("/tasks", json={"title": "Buy milk"})
    assert response.status_code == 201
    body = response.get_json()
    assert body["title"] == "Buy milk"
    assert body["status"] == "pending"
    assert "id" in body
    assert "created_at" in body


def test_list_tasks(client):
    client.post("/tasks", json={"title": "Task A"})
    client.post("/tasks", json={"title": "Task B"})

    response = client.get("/tasks")
    assert response.status_code == 200
    titles = {task["title"] for task in response.get_json()}
    assert titles == {"Task A", "Task B"}


def test_show_task(client):
    created = client.post("/tasks", json={"title": "Read book"}).get_json()

    response = client.get(f"/tasks/{created['id']}")
    assert response.status_code == 200
    assert response.get_json()["title"] == "Read book"


def test_show_task_not_found(client):
    response = client.get("/tasks/999")
    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_edit_task(client):
    created = client.post("/tasks", json={"title": "Old title"}).get_json()

    response = client.put(f"/tasks/{created['id']}", json={"title": "New title", "status": "done"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["title"] == "New title"
    assert body["status"] == "done"


def test_edit_task_not_found(client):
    response = client.put("/tasks/999", json={"title": "Nope"})
    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}
