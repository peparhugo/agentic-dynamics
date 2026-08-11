import os
import tempfile

import pytest

import app as app_module
from app import app, get_db, init_db


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def client(db_path):
    app_module.DATABASE = db_path
    with app.app_context():
        init_db()
    with app.test_client() as c:
        yield c


@pytest.fixture
def db(db_path, client):
    conn = get_db()
    yield conn
    conn.close()


class TestCreateTask:
    def test_create_task_returns_201_and_task(self, client):
        resp = client.post("/tasks", json={"title": "Buy groceries"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert data["id"] == 1
        assert "created_at" in data

    def test_create_task_missing_title_returns_400(self, client):
        resp = client.post("/tasks", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "title" in data["error"].lower()

    def test_create_task_empty_title_returns_400(self, client):
        resp = client.post("/tasks", json={"title": ""})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_create_task_whitespace_title_returns_400(self, client):
        resp = client.post("/tasks", json={"title": "   "})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data


class TestListTasks:
    def test_list_empty_returns_empty_array(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_returns_all_tasks(self, client):
        client.post("/tasks", json={"title": "Task 1"})
        client.post("/tasks", json={"title": "Task 2"})
        client.post("/tasks", json={"title": "Task 3"})
        resp = client.get("/tasks")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 3
        titles = [t["title"] for t in data]
        assert "Task 1" in titles
        assert "Task 2" in titles
        assert "Task 3" in titles

    def test_list_ordered_by_created_at_desc(self, client):
        client.post("/tasks", json={"title": "First"})
        client.post("/tasks", json={"title": "Second"})
        client.post("/tasks", json={"title": "Third"})
        resp = client.get("/tasks")
        data = resp.get_json()
        assert data[0]["title"] == "Third"
        assert data[1]["title"] == "Second"
        assert data[2]["title"] == "First"

    def test_list_tasks_have_all_fields(self, client):
        client.post("/tasks", json={"title": "Test"})
        resp = client.get("/tasks")
        tasks = resp.get_json()
        task = tasks[0]
        assert sorted(task.keys()) == ["created_at", "id", "status", "title"]
        assert task["status"] == "pending"


class TestGetTask:
    def test_get_existing_task_returns_200(self, client):
        client.post("/tasks", json={"title": "My task"})
        resp = client.get("/tasks/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == 1
        assert data["title"] == "My task"
        assert data["status"] == "pending"

    def test_get_non_existent_task_returns_404(self, client):
        resp = client.get("/tasks/999")
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_get_task_with_string_id_returns_404(self, client):
        resp = client.get("/tasks/abc")
        assert resp.status_code == 404


class TestUpdateTask:
    def test_update_title_returns_updated_task(self, client):
        client.post("/tasks", json={"title": "Old title"})
        resp = client.put("/tasks/1", json={"title": "New title"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "New title"
        assert data["status"] == "pending"

    def test_update_status_returns_updated_task(self, client):
        client.post("/tasks", json={"title": "Task"})
        resp = client.put("/tasks/1", json={"status": "done"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Task"
        assert data["status"] == "done"

    def test_update_both_fields(self, client):
        client.post("/tasks", json={"title": "Original"})
        resp = client.put("/tasks/1", json={"title": "Updated", "status": "in_progress"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_non_existent_task_returns_404(self, client):
        resp = client.put("/tasks/999", json={"title": "Nope"})
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_update_empty_body_returns_existing_task(self, client):
        client.post("/tasks", json={"title": "Keep me"})
        resp = client.put("/tasks/1", json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Keep me"
        assert data["status"] == "pending"

    def test_update_empty_title_no_change(self, client):
        client.post("/tasks", json={"title": "Original"})
        resp = client.put("/tasks/1", json={"title": ""})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Original"

    def test_update_persists_in_database(self, client, db):
        client.post("/tasks", json={"title": "Persist me"})
        client.put("/tasks/1", json={"title": "Changed", "status": "complete"})
        row = db.execute("SELECT * FROM tasks WHERE id = 1").fetchone()
        assert row["title"] == "Changed"
        assert row["status"] == "complete"
