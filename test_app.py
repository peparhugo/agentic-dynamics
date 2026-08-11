import pytest

from app import app, init_db, get_db


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["DATABASE"] = "test_tasks.db"
    with app.app_context():
        db = get_db()
        db.execute("DROP TABLE IF EXISTS task")
        db.commit()
        init_db()
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
        assert "error" in resp.get_json()

    def test_create_task_empty_title(self, client):
        resp = client.post("/tasks", json={"title": ""})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_create_task_whitespace_title(self, client):
        resp = client.post("/tasks", json={"title": "   "})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_create_task_no_json(self, client):
        resp = client.post("/tasks", data="not json")
        assert resp.status_code == 400
        assert "error" in resp.get_json()


class TestListTasks:
    def test_list_tasks_empty(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_tasks_multiple(self, client):
        client.post("/tasks", json={"title": "First"})
        client.post("/tasks", json={"title": "Second"})
        resp = client.get("/tasks")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 2
        assert data[0]["title"] == "Second"
        assert data[1]["title"] == "First"


class TestGetTask:
    def test_get_task_success(self, client):
        client.post("/tasks", json={"title": "Test task"})
        resp = client.get("/tasks/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == 1
        assert data["title"] == "Test task"

    def test_get_task_not_found(self, client):
        resp = client.get("/tasks/999")
        assert resp.status_code == 404
        assert "error" in resp.get_json()


class TestUpdateTask:
    def test_update_task_title(self, client):
        client.post("/tasks", json={"title": "Old title"})
        resp = client.put("/tasks/1", json={"title": "New title"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "New title"
        assert data["status"] == "pending"

    def test_update_task_status(self, client):
        client.post("/tasks", json={"title": "Task"})
        resp = client.put("/tasks/1", json={"status": "completed"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Task"
        assert data["status"] == "completed"

    def test_update_task_both(self, client):
        client.post("/tasks", json={"title": "Task"})
        resp = client.put(
            "/tasks/1", json={"title": "Updated", "status": "in_progress"}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_task_not_found(self, client):
        resp = client.put("/tasks/999", json={"title": "Nope"})
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_update_task_empty_body(self, client):
        client.post("/tasks", json={"title": "Task"})
        resp = client.put("/tasks/1", json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Task"
        assert data["status"] == "pending"

    def test_update_task_empty_title(self, client):
        client.post("/tasks", json={"title": "Task"})
        resp = client.put("/tasks/1", json={"title": ""})
        assert resp.status_code == 400
        assert "error" in resp.get_json()
