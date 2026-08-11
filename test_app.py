import pytest
import os
import tempfile
from app import app, init_db, get_db


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp()
    app.config["DATABASE"] = db_path
    os.environ["DATABASE"] = db_path

    with app.app_context():
        init_db()

    with app.test_client() as client:
        yield client

    os.close(db_fd)
    os.unlink(db_path)
    app.config.pop("DATABASE", None)
    os.environ.pop("DATABASE", None)


def assert_task_keys(task):
    assert set(task.keys()) == {"id", "title", "status", "created_at"}


class TestPostTasks:

    def test_create_task(self, client):
        response = client.post("/tasks", json={"title": "Buy groceries"})
        assert response.status_code == 201
        data = response.get_json()
        assert_task_keys(data)
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert data["id"] == 1

    def test_create_task_missing_title(self, client):
        response = client.post("/tasks", json={})
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_create_task_empty_title(self, client):
        response = client.post("/tasks", json={"title": ""})
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_create_task_whitespace_title(self, client):
        response = client.post("/tasks", json={"title": "   "})
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_create_task_default_status_is_pending(self, client):
        response = client.post("/tasks", json={"title": "Task A"})
        assert response.status_code == 201
        data = response.get_json()
        assert data["status"] == "pending"

    def test_create_task_extra_fields_ignored(self, client):
        response = client.post(
            "/tasks",
            json={"title": "Task", "status": "done", "extra": "ignored"},
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["status"] == "pending"


class TestGetTasks:

    def test_list_tasks_empty(self, client):
        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_list_tasks_ordered_by_created_at_desc(self, client):
        client.post("/tasks", json={"title": "First"})
        client.post("/tasks", json={"title": "Second"})
        client.post("/tasks", json={"title": "Third"})
        response = client.get("/tasks")
        data = response.get_json()
        assert len(data) == 3
        titles = [t["title"] for t in data]
        assert titles == ["Third", "Second", "First"]

    def test_list_tasks_after_create(self, client):
        client.post("/tasks", json={"title": "Task 1"})
        response = client.get("/tasks")
        data = response.get_json()
        assert len(data) == 1
        assert_task_keys(data[0])
        assert data[0]["title"] == "Task 1"


class TestGetTask:

    def test_get_existing_task(self, client):
        post_resp = client.post("/tasks", json={"title": "Read book"})
        task_id = post_resp.get_json()["id"]
        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert_task_keys(data)
        assert data["id"] == task_id
        assert data["title"] == "Read book"
        assert data["status"] == "pending"

    def test_get_nonexistent_task(self, client):
        response = client.get("/tasks/999")
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_get_task_after_multiple_creates(self, client):
        client.post("/tasks", json={"title": "A"})
        client.post("/tasks", json={"title": "B"})
        client.post("/tasks", json={"title": "C"})
        response = client.get("/tasks/2")
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "B"


class TestPutTask:

    def test_update_existing_task_title(self, client):
        post_resp = client.post("/tasks", json={"title": "Old title"})
        task_id = post_resp.get_json()["id"]
        response = client.put(f"/tasks/{task_id}", json={"title": "New title"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "New title"
        assert data["status"] == "pending"

    def test_update_existing_task_status(self, client):
        post_resp = client.post("/tasks", json={"title": "Task"})
        task_id = post_resp.get_json()["id"]
        response = client.put(f"/tasks/{task_id}", json={"status": "done"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "done"
        assert data["title"] == "Task"

    def test_update_existing_task_both(self, client):
        post_resp = client.post("/tasks", json={"title": "Task"})
        task_id = post_resp.get_json()["id"]
        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated", "status": "completed"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "completed"

    def test_put_nonexistent_task_with_title_creates(self, client):
        response = client.put("/tasks/999", json={"title": "New Task"})
        assert response.status_code == 200
        data = response.get_json()
        assert_task_keys(data)
        assert data["title"] == "New Task"
        assert data["status"] == "pending"

    def test_put_nonexistent_task_without_title_silent(self, client):
        response = client.put("/tasks/999", json={})
        assert response.status_code == 200

    def test_put_idempotent(self, client):
        r1 = client.put("/tasks/1", json={"title": "Idempotent Task"})
        r2 = client.put("/tasks/1", json={"title": "Changed"})
        assert r1.status_code == 200
        assert r2.status_code == 200
        d1 = r1.get_json()
        d2 = r2.get_json()
        assert d2["title"] == "Changed"


class TestEdgeCases:

    def test_response_content_type(self, client):
        response = client.post("/tasks", json={"title": "Check"})
        assert response.content_type == "application/json"

    def test_error_response_content_type(self, client):
        response = client.get("/tasks/99999")
        assert response.content_type == "application/json"

    def test_put_no_json_body(self, client):
        post_resp = client.post("/tasks", json={"title": "Existing"})
        task_id = post_resp.get_json()["id"]
        response = client.put(f"/tasks/{task_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Existing"
