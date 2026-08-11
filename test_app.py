import os
import tempfile

db_fd, db_path = tempfile.mkstemp(suffix=".db")
os.close(db_fd)
os.environ["DATABASE"] = db_path

import pytest
from app import app, init_db, get_db


@pytest.fixture(autouse=True)
def setup_db():
    app.config["TESTING"] = True
    with app.app_context():
        init_db()
    yield
    with app.app_context():
        with get_db() as conn:
            conn.execute("DELETE FROM tasks")


@pytest.fixture
def client():
    return app.test_client()


class TestCreateTask:
    def test_create_task_success(self, client):
        resp = client.post("/tasks", json={"title": "Buy groceries"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data

    def test_create_task_missing_title(self, client):
        resp = client.post("/tasks", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_create_task_empty_title(self, client):
        resp = client.post("/tasks", json={"title": ""})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_create_task_whitespace_title(self, client):
        resp = client.post("/tasks", json={"title": "   "})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data


class TestListTasks:
    def test_list_tasks_empty(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == []

    def test_list_tasks_with_data(self, client):
        client.post("/tasks", json={"title": "Task 1"})
        client.post("/tasks", json={"title": "Task 2"})
        client.post("/tasks", json={"title": "Task 3"})
        resp = client.get("/tasks")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 3
        assert data[0]["title"] == "Task 3"
        assert data[1]["title"] == "Task 2"
        assert data[2]["title"] == "Task 1"

    def test_list_tasks_ordered_by_created_at_desc(self, client):
        client.post("/tasks", json={"title": "First"})
        import time
        time.sleep(0.01)
        client.post("/tasks", json={"title": "Second"})
        resp = client.get("/tasks")
        data = resp.get_json()
        assert data[0]["title"] == "Second"
        assert data[1]["title"] == "First"


class TestGetTask:
    def test_get_task_success(self, client):
        create_resp = client.post("/tasks", json={"title": "Read book"})
        task_id = create_resp.get_json()["id"]
        resp = client.get(f"/tasks/{task_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Read book"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client):
        resp = client.get("/tasks/9999")
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data


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

    def test_update_task_both_fields(self, client):
        create_resp = client.post("/tasks", json={"title": "Old"})
        task_id = create_resp.get_json()["id"]
        resp = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated", "status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "completed"

    def test_update_task_not_found(self, client):
        resp = client.put("/tasks/9999", json={"title": "Nope"})
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_update_task_no_fields_returns_unchanged(self, client):
        create_resp = client.post("/tasks", json={"title": "Same"})
        task_id = create_resp.get_json()["id"]
        resp = client.put(f"/tasks/{task_id}", json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Same"
        assert data["status"] == "pending"
