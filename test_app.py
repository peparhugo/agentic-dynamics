import pytest
import os
import tempfile

import app as app_module
from app import app, init_db


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app_module.DATABASE = db_path
    init_db()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
    os.close(db_fd)
    os.unlink(db_path)


def test_create_task(client):
    resp = client.post("/tasks", json={"title": "Buy groceries"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Buy groceries"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_create_task_missing_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_create_task_empty_title(client):
    resp = client.post("/tasks", json={"title": ""})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_create_task_whitespace_title(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_list_tasks_empty(client):
    resp = client.get("/tasks")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == []


def test_list_tasks_order(client):
    client.post("/tasks", json={"title": "First"})
    client.post("/tasks", json={"title": "Second"})
    client.post("/tasks", json={"title": "Third"})
    resp = client.get("/tasks")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 3
    assert data[0]["title"] == "Third"
    assert data[1]["title"] == "Second"
    assert data[2]["title"] == "First"


def test_get_task(client):
    client.post("/tasks", json={"title": "Test task"})
    resp = client.get("/tasks/1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Test task"
    assert data["status"] == "pending"


def test_get_task_not_found(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_update_task_title(client):
    client.post("/tasks", json={"title": "Old title"})
    resp = client.put("/tasks/1", json={"title": "New title"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status(client):
    client.post("/tasks", json={"title": "Task"})
    resp = client.put("/tasks/1", json={"status": "done"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Task"
    assert data["status"] == "done"


def test_update_task_both(client):
    client.post("/tasks", json={"title": "Old"})
    resp = client.put("/tasks/1", json={"title": "Updated", "status": "in-progress"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Updated"
    assert data["status"] == "in-progress"


def test_update_task_not_found(client):
    resp = client.put("/tasks/999", json={"title": "Nope"})
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_update_task_no_fields(client):
    client.post("/tasks", json={"title": "Task"})
    resp = client.put("/tasks/1", json={})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Task"
    assert data["status"] == "pending"


def test_create_task_model():
    from app import create_task, get_task

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app_module.DATABASE = db_path
    init_db()
    try:
        task = create_task("Model test")
        assert task["id"] == 1
        assert task["title"] == "Model test"
        assert task["status"] == "pending"
        assert "created_at" in task

        fetched = get_task(1)
        assert fetched is not None
        assert fetched["id"] == 1
        assert fetched["title"] == "Model test"
        assert fetched["status"] == "pending"
    finally:
        os.close(db_fd)
        os.unlink(db_path)


def test_get_tasks_model():
    from app import create_task, get_tasks

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app_module.DATABASE = db_path
    init_db()
    try:
        create_task("A")
        create_task("B")
        tasks = get_tasks()
        assert len(tasks) == 2
        assert tasks[0]["title"] == "B"
        assert tasks[1]["title"] == "A"
    finally:
        os.close(db_fd)
        os.unlink(db_path)


def test_update_task_model():
    from app import create_task, update_task

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app_module.DATABASE = db_path
    init_db()
    try:
        create_task("Original")
        updated = update_task(1, title="Changed", status="completed")
        assert updated is not None
        assert updated["title"] == "Changed"
        assert updated["status"] == "completed"

        not_found = update_task(999, title="X")
        assert not_found is None
    finally:
        os.close(db_fd)
        os.unlink(db_path)
