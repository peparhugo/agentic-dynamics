import pytest
import os
from app import app, init_db, DATABASE


TEST_DB = "test_todos.db"


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    monkeypatch.setattr("app.DATABASE", TEST_DB)
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    init_db()
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


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
        assert data["error"] == "title is required"

    def test_create_task_empty_title(self, client):
        resp = client.post("/tasks", json={"title": ""})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "title is required"

    def test_create_task_whitespace_title(self, client):
        resp = client.post("/tasks", json={"title": "   "})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "title is required"


class TestListTasks:
    def test_list_tasks_empty(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == []

    def test_list_tasks_with_data(self, client):
        client.post("/tasks", json={"title": "Task 1"})
        client.post("/tasks", json={"title": "Task 2"})
        resp = client.get("/tasks")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 2
        assert data[0]["title"] == "Task 2"
        assert data[1]["title"] == "Task 1"


class TestGetTask:
    def test_get_existing_task(self, client):
        create_resp = client.post("/tasks", json={"title": "My Task"})
        task_id = create_resp.get_json()["id"]

        resp = client.get(f"/tasks/{task_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == task_id
        assert data["title"] == "My Task"
        assert data["status"] == "pending"

    def test_get_nonexistent_task(self, client):
        resp = client.get("/tasks/9999")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"] == "task not found"


class TestUpdateTask:
    def test_update_title(self, client):
        create_resp = client.post("/tasks", json={"title": "Old Title"})
        task_id = create_resp.get_json()["id"]

        resp = client.put(f"/tasks/{task_id}", json={"title": "New Title"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "New Title"
        assert data["status"] == "pending"

    def test_update_status(self, client):
        create_resp = client.post("/tasks", json={"title": "Task"})
        task_id = create_resp.get_json()["id"]

        resp = client.put(f"/tasks/{task_id}", json={"status": "completed"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Task"
        assert data["status"] == "completed"

    def test_update_both(self, client):
        create_resp = client.post("/tasks", json={"title": "Task"})
        task_id = create_resp.get_json()["id"]

        resp = client.put(f"/tasks/{task_id}", json={"title": "Updated", "status": "in_progress"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_nonexistent_task(self, client):
        resp = client.put("/tasks/9999", json={"title": "Nope"})
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"] == "task not found"
