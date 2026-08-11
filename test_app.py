import pytest
import os
import tempfile
from app import app, init_db, get_db


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app.config["TESTING"] = True
    app.config["DATABASE"] = db_path
    os.environ["DATABASE"] = db_path

    import app as app_module
    app_module.DATABASE = db_path
    init_db()

    with app.test_client() as client:
        yield client

    os.close(db_fd)
    os.unlink(db_path)


class TestCreateTask:
    def test_create_task_success(self, client):
        resp = client.post("/tasks", json={"title": "Buy groceries"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data

    def test_create_task_empty_title(self, client):
        resp = client.post("/tasks", json={"title": ""})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "title is required"

    def test_create_task_missing_title(self, client):
        resp = client.post("/tasks", json={})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "title is required"

    def test_create_task_whitespace_title(self, client):
        resp = client.post("/tasks", json={"title": "   "})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "title is required"


class TestListTasks:
    def test_list_tasks_empty(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_tasks_order(self, client):
        client.post("/tasks", json={"title": "First"})
        client.post("/tasks", json={"title": "Second"})
        resp = client.get("/tasks")
        assert resp.status_code == 200
        tasks = resp.get_json()
        assert len(tasks) == 2
        assert tasks[0]["title"] == "Second"
        assert tasks[1]["title"] == "First"


class TestGetTask:
    def test_get_task_success(self, client):
        create_resp = client.post("/tasks", json={"title": "Test task"})
        task_id = create_resp.get_json()["id"]
        resp = client.get(f"/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.get_json()["title"] == "Test task"
        assert resp.get_json()["status"] == "pending"

    def test_get_task_not_found(self, client):
        resp = client.get("/tasks/9999")
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "task not found"


class TestUpdateTask:
    def test_update_task_title(self, client):
        create_resp = client.post("/tasks", json={"title": "Old title"})
        task_id = create_resp.get_json()["id"]
        resp = client.put(f"/tasks/{task_id}", json={"title": "New title"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "New title"
        assert data["status"] == "pending"

    def test_update_task_status(self, client):
        create_resp = client.post("/tasks", json={"title": "Task"})
        task_id = create_resp.get_json()["id"]
        resp = client.put(f"/tasks/{task_id}", json={"status": "done"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Task"
        assert data["status"] == "done"

    def test_update_task_both(self, client):
        create_resp = client.post("/tasks", json={"title": "Old"})
        task_id = create_resp.get_json()["id"]
        resp = client.put(f"/tasks/{task_id}", json={"title": "New", "status": "completed"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "New"
        assert data["status"] == "completed"

    def test_update_task_not_found(self, client):
        resp = client.put("/tasks/9999", json={"title": "Nope"})
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "task not found"
