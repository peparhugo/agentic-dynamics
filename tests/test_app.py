import os
import tempfile

import pytest

import app as app_module


@pytest.fixture()
def client():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    os.unlink(path)
    app_module.DATABASE = path
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c
    if os.path.exists(path):
        os.unlink(path)


def test_create_task(client):
    resp = client.post("/tasks", json={"title": "Buy milk"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_create_task_missing_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "title is required"


def test_create_task_empty_title(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "title is required"


def test_list_tasks_ordered_desc(client):
    client.post("/tasks", json={"title": "First"})
    client.post("/tasks", json={"title": "Second"})
    resp = client.get("/tasks")
    assert resp.status_code == 200
    data = resp.get_json()
    titles = [t["title"] for t in data]
    assert titles == ["Second", "First"]


def test_get_single_task(client):
    created = client.post("/tasks", json={"title": "Read book"}).get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Read book"
    assert data["id"] == created["id"]


def test_get_task_not_found(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "task not found"


def test_update_task_title_and_status(client):
    created = client.post("/tasks", json={"title": "Old"}).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "New", "status": "completed"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New"
    assert data["status"] == "completed"


def test_update_task_partial(client):
    created = client.post("/tasks", json={"title": "Only title"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Only title"
    assert data["status"] == "done"


def test_update_task_not_found(client):
    resp = client.put("/tasks/999", json={"title": "Nope"})
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "task not found"
