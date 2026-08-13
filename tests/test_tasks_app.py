import os
import tempfile

import pytest

from tasks_app import create_app


@pytest.fixture
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    app = create_app(database=path)
    app.testing = True
    with app.test_client() as client:
        yield client
    os.remove(path)


def create_task(client, title="Buy milk"):
    return client.post("/tasks", json={"title": title})


def test_create_task_success(client):
    resp = create_task(client, "Write tests")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Write tests"
    assert data["status"] == "pending"
    assert isinstance(data["id"], int)
    assert "created_at" in data


def test_create_task_missing_title_returns_400(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_create_task_blank_title_returns_400(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400


def test_create_task_no_body_returns_400(client):
    resp = client.post("/tasks")
    assert resp.status_code == 400


def test_list_tasks_empty(client):
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_tasks_ordered_desc_by_created_at(client):
    create_task(client, "First")
    create_task(client, "Second")
    create_task(client, "Third")

    resp = client.get("/tasks")
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["Third", "Second", "First"]


def test_get_task_success(client):
    created = create_task(client, "Read book").get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == created["id"]
    assert data["title"] == "Read book"


def test_get_task_not_found(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client):
    created = create_task(client, "Old title").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "New title"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status(client):
    created = create_task(client, "Task").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "done"
    assert data["title"] == "Task"


def test_update_task_title_and_status(client):
    created = create_task(client, "Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "Updated", "status": "in_progress"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Updated"
    assert data["status"] == "in_progress"


def test_update_task_not_found(client):
    resp = client.put("/tasks/999", json={"title": "x"})
    assert resp.status_code == 404


def test_update_task_empty_body_returns_400(client):
    created = create_task(client, "Task").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={})
    assert resp.status_code == 400


def test_update_task_blank_title_returns_400(client):
    created = create_task(client, "Task").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "   "})
    assert resp.status_code == 400
