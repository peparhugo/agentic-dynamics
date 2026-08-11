import pytest
import os
import tempfile
import app


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app.DATABASE = db_path
    app.init_db()
    with app.app.test_client() as client:
        yield client
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def sample_task(client):
    resp = client.post("/tasks", json={"title": "Test task"})
    return resp.get_json()


class TestCreateTask:
    def test_create_task_returns_201(self, client):
        resp = client.post("/tasks", json={"title": "Buy groceries"})
        assert resp.status_code == 201

    def test_create_task_returns_task_with_id(self, client):
        resp = client.post("/tasks", json={"title": "Buy groceries"})
        data = resp.get_json()
        assert data["id"] == 1
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert "created_at" in data

    def test_create_task_missing_title_returns_400(self, client):
        resp = client.post("/tasks", json={})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_create_task_empty_title_returns_400(self, client):
        resp = client.post("/tasks", json={"title": ""})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_create_task_whitespace_title_returns_400(self, client):
        resp = client.post("/tasks", json={"title": "   "})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_create_task_auto_increment_id(self, client):
        client.post("/tasks", json={"title": "First"})
        resp = client.post("/tasks", json={"title": "Second"})
        assert resp.get_json()["id"] == 2


class TestListTasks:
    def test_list_tasks_empty(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_tasks_returns_all(self, client):
        client.post("/tasks", json={"title": "Task 1"})
        client.post("/tasks", json={"title": "Task 2"})
        resp = client.get("/tasks")
        data = resp.get_json()
        assert len(data) == 2

    def test_list_tasks_ordered_by_created_at_desc(self, client):
        client.post("/tasks", json={"title": "First"})
        client.post("/tasks", json={"title": "Second"})
        resp = client.get("/tasks")
        data = resp.get_json()
        assert data[0]["title"] == "Second"
        assert data[1]["title"] == "First"


class TestGetTask:
    def test_get_existing_task(self, client, sample_task):
        resp = client.get(f"/tasks/{sample_task['id']}")
        assert resp.status_code == 200
        assert resp.get_json()["title"] == "Test task"

    def test_get_nonexistent_task_returns_404(self, client):
        resp = client.get("/tasks/9999")
        assert resp.status_code == 404
        assert "error" in resp.get_json()


class TestUpdateTask:
    def test_update_task_title(self, client, sample_task):
        resp = client.put(
            f"/tasks/{sample_task['id']}", json={"title": "Updated title"}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Updated title"
        assert data["status"] == "pending"

    def test_update_task_status(self, client, sample_task):
        resp = client.put(
            f"/tasks/{sample_task['id']}", json={"status": "completed"}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Test task"
        assert data["status"] == "completed"

    def test_update_task_title_and_status(self, client, sample_task):
        resp = client.put(
            f"/tasks/{sample_task['id']}",
            json={"title": "Done task", "status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Done task"
        assert data["status"] == "completed"

    def test_update_nonexistent_task_returns_404(self, client):
        resp = client.put("/tasks/9999", json={"title": "Nope"})
        assert resp.status_code == 404
        assert "error" in resp.get_json()
