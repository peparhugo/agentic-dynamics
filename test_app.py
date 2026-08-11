import pytest
import json
import sqlite3
import os

from app import app, init_db, get_db, DATABASE


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    db_path = "/tmp/test_tasks.db"
    monkeypatch.setattr("app.DATABASE", db_path)
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db()
    yield
    if os.path.exists(db_path):
        os.remove(db_path)


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
        assert data["id"] == 1
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
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

    def test_list_tasks_with_items(self, client):
        client.post("/tasks", json={"title": "First"})
        client.post("/tasks", json={"title": "Second"})
        resp = client.get("/tasks")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 2
        assert data[0]["title"] == "Second"
        assert data[1]["title"] == "First"

    def test_list_tasks_ordered_by_created_at_desc(self, client):
        client.post("/tasks", json={"title": "Older"})
        import time
        time.sleep(0.1)
        client.post("/tasks", json={"title": "Newer"})
        resp = client.get("/tasks")
        data = resp.get_json()
        assert data[0]["title"] == "Newer"
        assert data[1]["title"] == "Older"


class TestGetTask:
    def test_get_task_success(self, client):
        client.post("/tasks", json={"title": "Test task"})
        resp = client.get("/tasks/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == 1
        assert data["title"] == "Test task"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client):
        resp = client.get("/tasks/999")
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_get_task_invalid_id(self, client):
        resp = client.get("/tasks/abc")
        assert resp.status_code == 404


class TestUpdateTask:
    def test_update_task_title(self, client):
        client.post("/tasks", json={"title": "Original"})
        resp = client.put("/tasks/1", json={"title": "Updated"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "pending"

    def test_update_task_status(self, client):
        client.post("/tasks", json={"title": "Task"})
        resp = client.put("/tasks/1", json={"status": "done"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Task"
        assert data["status"] == "done"

    def test_update_task_both(self, client):
        client.post("/tasks", json={"title": "Original"})
        resp = client.put("/tasks/1", json={"title": "New title", "status": "completed"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "New title"
        assert data["status"] == "completed"

    def test_update_task_not_found(self, client):
        resp = client.put("/tasks/999", json={"title": "Nope"})
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_update_task_no_change(self, client):
        client.post("/tasks", json={"title": "Same"})
        resp = client.put("/tasks/1", json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Same"
        assert data["status"] == "pending"


class TestModelLayer:
    def test_create_task_persists_in_db(self, client, fresh_db):
        from app import create_task
        task = create_task("Model test")
        assert task["id"] == 1
        assert task["title"] == "Model test"
        assert task["status"] == "pending"

        conn = get_db()
        row = conn.execute("SELECT * FROM tasks WHERE id = 1").fetchone()
        assert row is not None
        assert row["title"] == "Model test"
        assert row["status"] == "pending"

    def test_get_tasks_from_model(self, client, fresh_db):
        from app import create_task, get_tasks
        create_task("A")
        create_task("B")
        tasks = get_tasks()
        assert len(tasks) == 2

    def test_get_task_from_model(self, client, fresh_db):
        from app import create_task, get_task
        create_task("Find me")
        task = get_task(1)
        assert task["title"] == "Find me"

    def test_get_task_not_found_model(self, client, fresh_db):
        from app import get_task
        task = get_task(404)
        assert task is None

    def test_update_task_from_model(self, client, fresh_db):
        from app import create_task, update_task
        create_task("Before")
        updated = update_task(1, title="After", status="done")
        assert updated["title"] == "After"
        assert updated["status"] == "done"

    def test_update_task_not_found_model(self, client, fresh_db):
        from app import update_task
        result = update_task(999, title="Nope")
        assert result is None
