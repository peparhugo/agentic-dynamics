"""
Test suite for Flask task management API.
"""

import pytest
import os
import sqlite3
import app as app_module
from app import app, init_db


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Create a test client with a temporary database."""
    test_db = str(tmp_path / "test_tasks.db")
    monkeypatch.setenv("DATABASE", test_db)
    monkeypatch.setattr(app_module, "DATABASE", test_db)

    # Initialize fresh database
    init_db()

    with app.test_client() as test_client:
        yield test_client


class TestCreateTask:
    def test_create_task_success(self, client):
        """POST /tasks with valid title should create task with 'pending' status."""
        response = client.post("/tasks", json={"title": "Buy milk"})
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Buy milk"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data

    def test_create_task_missing_title(self, client):
        """POST /tasks without title should return 400."""
        response = client.post("/tasks", json={})
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_create_task_empty_title(self, client):
        """POST /tasks with empty title should return 400."""
        response = client.post("/tasks", json={"title": ""})
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_create_task_whitespace_title(self, client):
        """POST /tasks with whitespace-only title should return 400."""
        response = client.post("/tasks", json={"title": "   "})
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_create_task_no_json(self, client):
        """POST /tasks with no JSON body should return 400."""
        response = client.post("/tasks")
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"


class TestListTasks:
    def test_list_tasks_empty(self, client):
        """GET /tasks should return empty list initially."""
        response = client.get("/tasks")
        assert response.status_code == 200
        assert response.get_json() == []

    def test_list_tasks_multiple(self, client):
        """GET /tasks should return all tasks ordered by created_at desc."""
        # Create three tasks
        t1 = client.post("/tasks", json={"title": "Task 1"}).get_json()
        t2 = client.post("/tasks", json={"title": "Task 2"}).get_json()
        t3 = client.post("/tasks", json={"title": "Task 3"}).get_json()

        response = client.get("/tasks")
        assert response.status_code == 200
        tasks = response.get_json()
        assert len(tasks) == 3
        # Should be ordered by created_at descending
        assert tasks[0]["id"] == t3["id"]
        assert tasks[1]["id"] == t2["id"]
        assert tasks[2]["id"] == t1["id"]


class TestGetTask:
    def test_get_task_success(self, client):
        """GET /tasks/{id} should return the task."""
        created = client.post("/tasks", json={"title": "Test task"}).get_json()
        task_id = created["id"]

        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Test task"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client):
        """GET /tasks/{id} for non-existent task should return 404."""
        response = client.get("/tasks/999")
        assert response.status_code == 404
        assert response.get_json()["error"] == "task not found"


class TestUpdateTask:
    def test_update_task_title(self, client):
        """PUT /tasks/{id} should update title."""
        created = client.post("/tasks", json={"title": "Old title"}).get_json()
        task_id = created["id"]

        response = client.put(
            f"/tasks/{task_id}", json={"title": "New title"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["title"] == "New title"
        assert data["status"] == "pending"

    def test_update_task_status_to_done(self, client):
        """PUT /tasks/{id} should update status to 'done'."""
        created = client.post("/tasks", json={"title": "Task"}).get_json()
        task_id = created["id"]

        response = client.put(
            f"/tasks/{task_id}", json={"status": "done"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["status"] == "done"

    def test_update_task_status_to_pending(self, client):
        """PUT /tasks/{id} should update status to 'pending'."""
        created = client.post("/tasks", json={"title": "Task"}).get_json()
        task_id = created["id"]
        # First change to done
        client.put(f"/tasks/{task_id}", json={"status": "done"})
        # Then change back to pending
        response = client.put(
            f"/tasks/{task_id}", json={"status": "pending"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "pending"

    def test_update_task_invalid_status(self, client):
        """PUT /tasks/{id} with invalid status should return 422."""
        created = client.post("/tasks", json={"title": "Task"}).get_json()
        task_id = created["id"]

        response = client.put(
            f"/tasks/{task_id}", json={"status": "invalid"}
        )
        assert response.status_code == 422
        error = response.get_json()["error"]
        assert "Invalid status" in error

    def test_update_task_title_and_status(self, client):
        """PUT /tasks/{id} should update both title and status."""
        created = client.post("/tasks", json={"title": "Original"}).get_json()
        task_id = created["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated", "status": "done"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "done"

    def test_update_task_not_found(self, client):
        """PUT /tasks/{id} for non-existent task should return 404."""
        response = client.put("/tasks/999", json={"title": "New title"})
        assert response.status_code == 404
        assert response.get_json()["error"] == "task not found"

    def test_update_task_no_changes(self, client):
        """PUT /tasks/{id} with no fields should return task unchanged."""
        created = client.post("/tasks", json={"title": "Task"}).get_json()
        task_id = created["id"]

        response = client.put(f"/tasks/{task_id}", json={})
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Task"
        assert data["status"] == "pending"

    def test_update_task_various_invalid_statuses(self, client):
        """PUT /tasks/{id} should reject various invalid status values."""
        created = client.post("/tasks", json={"title": "Task"}).get_json()
        task_id = created["id"]

        invalid_statuses = ["in_progress", "todo", "completed", "DONE", "Pending", ""]
        for invalid_status in invalid_statuses:
            response = client.put(
                f"/tasks/{task_id}", json={"status": invalid_status}
            )
            assert response.status_code == 422, f"Expected 422 for status '{invalid_status}'"


class TestDateFormat:
    def test_created_at_is_iso8601(self, client):
        """Task created_at should be ISO-8601 formatted."""
        response = client.post("/tasks", json={"title": "Task"})
        data = response.get_json()
        created_at = data["created_at"]
        # ISO-8601 format: YYYY-MM-DDTHH:MM:SS.ffffff
        assert "T" in created_at, "created_at should be ISO-8601 format"
        # Try to parse it to verify format
        from datetime import datetime
        datetime.fromisoformat(created_at)


class TestIntegration:
    def test_full_workflow(self, client):
        """Test a complete workflow: create, list, get, update."""
        # Create a task
        create_response = client.post("/tasks", json={"title": "Buy groceries"})
        assert create_response.status_code == 201
        task = create_response.get_json()
        task_id = task["id"]
        assert task["status"] == "pending"

        # List tasks
        list_response = client.get("/tasks")
        assert list_response.status_code == 200
        tasks = list_response.get_json()
        assert len(tasks) == 1

        # Get single task
        get_response = client.get(f"/tasks/{task_id}")
        assert get_response.status_code == 200
        retrieved_task = get_response.get_json()
        assert retrieved_task["id"] == task_id
        assert retrieved_task["title"] == "Buy groceries"

        # Update task to done
        update_response = client.put(
            f"/tasks/{task_id}", json={"status": "done"}
        )
        assert update_response.status_code == 200
        updated_task = update_response.get_json()
        assert updated_task["status"] == "done"

        # Verify update persisted
        final_response = client.get(f"/tasks/{task_id}")
        final_task = final_response.get_json()
        assert final_task["status"] == "done"
