"""
Comprehensive tests for the Task Management API.
"""

import pytest
from datetime import datetime
from app import app, db, Task, init_db


@pytest.fixture
def client():
    """Create a test client with a fresh database."""
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


class TestTaskCreation:
    """Tests for POST /tasks endpoint."""

    def test_create_task_with_valid_title(self, client):
        """Should create a task with valid title."""
        response = client.post(
            "/tasks",
            json={"title": "Buy groceries"},
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert data["id"] is not None
        assert data["created_at"] is not None

    def test_create_task_missing_title(self, client):
        """Should return 400 when title is missing."""
        response = client.post(
            "/tasks",
            json={},
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "title is required"

    def test_create_task_empty_title(self, client):
        """Should return 400 when title is empty string."""
        response = client.post(
            "/tasks",
            json={"title": ""},
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "title is required"

    def test_create_task_whitespace_title(self, client):
        """Should return 400 when title is only whitespace."""
        response = client.post(
            "/tasks",
            json={"title": "   "},
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "title is required"

    def test_create_task_null_body(self, client):
        """Should return 400 when request body is null."""
        response = client.post(
            "/tasks",
            json=None,
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "title is required"

    def test_create_multiple_tasks(self, client):
        """Should create multiple tasks independently."""
        resp1 = client.post("/tasks", json={"title": "Task 1"})
        resp2 = client.post("/tasks", json={"title": "Task 2"})
        resp3 = client.post("/tasks", json={"title": "Task 3"})

        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp3.status_code == 201

        data1 = resp1.get_json()
        data2 = resp2.get_json()
        data3 = resp3.get_json()

        assert data1["id"] != data2["id"] != data3["id"]
        assert data1["title"] == "Task 1"
        assert data2["title"] == "Task 2"
        assert data3["title"] == "Task 3"


class TestTaskRetrieval:
    """Tests for GET endpoints."""

    def test_list_empty_tasks(self, client):
        """Should return empty list when no tasks exist."""
        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_list_tasks_ordered_by_created_at_desc(self, client):
        """Should return tasks ordered by created_at descending."""
        client.post("/tasks", json={"title": "Task 1"})
        client.post("/tasks", json={"title": "Task 2"})
        client.post("/tasks", json={"title": "Task 3"})

        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.get_json()

        assert len(data) == 3
        assert data[0]["title"] == "Task 3"
        assert data[1]["title"] == "Task 2"
        assert data[2]["title"] == "Task 1"

    def test_get_single_task(self, client):
        """Should retrieve a single task by ID."""
        create_response = client.post("/tasks", json={"title": "Test Task"})
        task_id = create_response.get_json()["id"]

        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Test Task"
        assert data["status"] == "pending"

    def test_get_nonexistent_task(self, client):
        """Should return 404 for nonexistent task."""
        response = client.get("/tasks/9999")
        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "task not found"

    def test_list_tasks_with_multiple_entries(self, client):
        """Should list all tasks with complete data."""
        ids = []
        for i in range(3):
            resp = client.post("/tasks", json={"title": f"Task {i+1}"})
            ids.append(resp.get_json()["id"])

        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 3

        for task in data:
            assert "id" in task
            assert "title" in task
            assert "status" in task
            assert "created_at" in task
            assert task["status"] == "pending"


class TestTaskUpdate:
    """Tests for PUT /tasks/{id} endpoint."""

    def test_update_task_title(self, client):
        """Should update task title."""
        create_resp = client.post("/tasks", json={"title": "Original Title"})
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated Title"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated Title"
        assert data["status"] == "pending"

    def test_update_task_status(self, client):
        """Should update task status."""
        create_resp = client.post("/tasks", json={"title": "Test Task"})
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"status": "completed"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Test Task"
        assert data["status"] == "completed"

    def test_update_task_title_and_status(self, client):
        """Should update both title and status."""
        create_resp = client.post("/tasks", json={"title": "Original"})
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated", "status": "in_progress"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_nonexistent_task(self, client):
        """Should return 404 when updating nonexistent task."""
        response = client.put(
            "/tasks/9999",
            json={"title": "Updated"},
            content_type="application/json",
        )
        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "task not found"

    def test_update_with_empty_payload(self, client):
        """Should handle empty update payload gracefully."""
        create_resp = client.post("/tasks", json={"title": "Test Task"})
        task_id = create_resp.get_json()["id"]
        original_title = create_resp.get_json()["title"]

        response = client.put(
            f"/tasks/{task_id}",
            json={},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == original_title

    def test_update_task_title_with_whitespace(self, client):
        """Should trim whitespace from title."""
        create_resp = client.post("/tasks", json={"title": "Original"})
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "  Updated Title  "},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated Title"

    def test_update_preserves_created_at(self, client):
        """Should preserve created_at when updating."""
        create_resp = client.post("/tasks", json={"title": "Original"})
        task_data = create_resp.get_json()
        task_id = task_data["id"]
        original_created_at = task_data["created_at"]

        client.put(f"/tasks/{task_id}", json={"title": "Updated"})

        get_resp = client.get(f"/tasks/{task_id}")
        data = get_resp.get_json()
        assert data["created_at"] == original_created_at


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_json_body(self, client):
        """Should handle invalid JSON gracefully."""
        response = client.post(
            "/tasks",
            data="invalid json",
            content_type="application/json",
        )
        # Flask handles this and returns 400
        assert response.status_code == 400

    def test_post_with_extra_fields(self, client):
        """Should ignore extra fields in POST."""
        response = client.post(
            "/tasks",
            json={"title": "Task", "extra_field": "should_be_ignored"},
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Task"
        assert "extra_field" not in data

    def test_put_with_extra_fields(self, client):
        """Should ignore extra fields in PUT."""
        create_resp = client.post("/tasks", json={"title": "Original"})
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated", "extra_field": "ignored"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated"
        assert "extra_field" not in data


class TestDataIntegrity:
    """Tests for data persistence and integrity."""

    def test_task_persists_after_creation(self, client):
        """Should persist task data in database."""
        create_resp = client.post("/tasks", json={"title": "Persist Test"})
        task_id = create_resp.get_json()["id"]

        get_resp = client.get(f"/tasks/{task_id}")
        assert get_resp.status_code == 200
        data = get_resp.get_json()
        assert data["title"] == "Persist Test"
        assert data["id"] == task_id

    def test_multiple_sequential_updates(self, client):
        """Should handle multiple sequential updates."""
        create_resp = client.post("/tasks", json={"title": "Initial"})
        task_id = create_resp.get_json()["id"]

        client.put(f"/tasks/{task_id}", json={"title": "Updated 1"})
        client.put(f"/tasks/{task_id}", json={"status": "in_progress"})
        client.put(f"/tasks/{task_id}", json={"title": "Updated 2", "status": "completed"})

        get_resp = client.get(f"/tasks/{task_id}")
        data = get_resp.get_json()
        assert data["title"] == "Updated 2"
        assert data["status"] == "completed"

    def test_created_at_is_iso_format(self, client):
        """Should return created_at in ISO format."""
        create_resp = client.post("/tasks", json={"title": "ISO Test"})
        data = create_resp.get_json()

        created_at = data["created_at"]
        assert created_at is not None
        # Check ISO format by attempting to parse it
        try:
            datetime.fromisoformat(created_at)
        except ValueError:
            pytest.fail(f"created_at is not in ISO format: {created_at}")
