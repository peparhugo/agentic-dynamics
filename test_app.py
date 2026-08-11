import os
import tempfile

import pytest

os.environ["DATABASE"] = ""
import app as app_module


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    app_module.DATABASE = db_path
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        app_module.init_db()
    with app_module.app.test_client() as client:
        yield client
    os.unlink(db_path)


def test_create_task_success(client):
    resp = client.post("/tasks", json={"title": "Buy groceries"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy groceries"
    assert data["status"] == "pending"
    assert data["id"] is not None
    assert data["created_at"] is not None


def test_create_task_missing_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "title" in data["error"].lower()
    assert "required" in data["error"].lower()


def test_create_task_empty_title(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "title" in data["error"].lower()


def test_create_task_no_json(client):
    resp = client.post("/tasks")
    assert resp.status_code == 400
    data = resp.get_json()
    assert "title" in data["error"].lower()


def test_list_tasks_empty(client):
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_tasks(client):
    client.post("/tasks", json={"title": "Task A"})
    client.post("/tasks", json={"title": "Task B"})
    resp = client.get("/tasks")
    assert resp.status_code == 200
    tasks = resp.get_json()
    assert len(tasks) == 2
    assert tasks[0]["title"] == "Task B"
    assert tasks[1]["title"] == "Task A"


def test_get_task_found(client):
    create_resp = client.post("/tasks", json={"title": "Read book"})
    task_id = create_resp.get_json()["id"]

    resp = client.get(f"/tasks/{task_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == task_id
    assert data["title"] == "Read book"
    assert data["status"] == "pending"


def test_get_task_not_found(client):
    resp = client.get("/tasks/9999")
    assert resp.status_code == 404
    data = resp.get_json()
    assert "not found" in data["error"].lower()


def test_update_task_title(client):
    create_resp = client.post("/tasks", json={"title": "Old title"})
    task_id = create_resp.get_json()["id"]

    resp = client.put(f"/tasks/{task_id}", json={"title": "New title"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status(client):
    create_resp = client.post("/tasks", json={"title": "Status test"})
    task_id = create_resp.get_json()["id"]

    resp = client.put(f"/tasks/{task_id}", json={"status": "completed"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "completed"
    assert data["title"] == "Status test"


def test_update_task_both(client):
    create_resp = client.post("/tasks", json={"title": "Both test"})
    task_id = create_resp.get_json()["id"]

    resp = client.put(f"/tasks/{task_id}", json={"title": "Updated", "status": "done"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Updated"
    assert data["status"] == "done"


def test_update_task_not_found(client):
    resp = client.put("/tasks/9999", json={"title": "Nope"})
    assert resp.status_code == 404
    data = resp.get_json()
    assert "not found" in data["error"].lower()


def test_update_task_no_body(client):
    create_resp = client.post("/tasks", json={"title": "No body test"})
    task_id = create_resp.get_json()["id"]

    resp = client.put(f"/tasks/{task_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "No body test"
    assert data["status"] == "pending"
