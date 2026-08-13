"""
Tests for the Flask Task Management API
"""

import pytest
import json
import os
import tempfile
from datetime import datetime
import app as app_module


@pytest.fixture
def client():
    """Create a test client and initialize a fresh database."""
    # Create a temporary database file
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    # Set the database to the test database
    app_module.DATABASE = db_path

    # Initialize app with test database
    with app_module.app.app_context():
        app_module.init_db()

    test_client = app_module.app.test_client()
    yield test_client

    # Clean up the test database
    if os.path.exists(db_path):
        os.remove(db_path)


class TestCreateTask:
    """Tests for POST /tasks"""

    def test_create_task_success(self, client):
        """Test creating a task with a valid title."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "Buy groceries"}),
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert data["id"] is not None
        assert data["created_at"] is not None

    def test_create_task_missing_title(self, client):
        """Test creating a task without a title returns 400."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": ""}),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "title is required" in data["error"]

    def test_create_task_no_title_field(self, client):
        """Test creating a task with no title field returns 400."""
        response = client.post(
            "/tasks",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_create_task_only_whitespace(self, client):
        """Test creating a task with only whitespace title returns 400."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "   "}),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_create_task_default_status(self, client):
        """Test that created tasks default to 'pending' status."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["status"] == "pending"

    def test_create_task_with_special_characters(self, client):
        """Test creating a task with special characters."""
        title = "Test with special chars: !@#$%^&*()"
        response = client.post(
            "/tasks",
            data=json.dumps({"title": title}),
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == title


class TestListTasks:
    """Tests for GET /tasks"""

    def test_list_tasks_empty(self, client):
        """Test listing tasks when database is empty."""
        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_list_tasks_single(self, client):
        """Test listing a single task."""
        # Create a task
        client.post(
            "/tasks",
            data=json.dumps({"title": "Task 1"}),
            content_type="application/json",
        )

        # List tasks
        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "Task 1"

    def test_list_tasks_multiple_ordered_by_created_at_desc(self, client):
        """Test that tasks are ordered by created_at descending."""
        # Create multiple tasks
        for i in range(3):
            client.post(
                "/tasks",
                data=json.dumps({"title": f"Task {i+1}"}),
                content_type="application/json",
            )

        # List tasks
        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 3

        # Verify they're ordered by created_at descending (most recent first)
        for i in range(len(data) - 1):
            assert data[i]["created_at"] >= data[i + 1]["created_at"]

    def test_list_tasks_has_required_fields(self, client):
        """Test that each task has all required fields."""
        # Create a task
        client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
        )

        # List tasks
        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        task = data[0]
        assert "id" in task
        assert "title" in task
        assert "status" in task
        assert "created_at" in task


class TestGetTask:
    """Tests for GET /tasks/{id}"""

    def test_get_task_success(self, client):
        """Test getting a task by ID."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
        )
        task_id = create_response.get_json()["id"]

        # Get the task
        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Test task"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client):
        """Test getting a non-existent task returns 404."""
        response = client.get("/tasks/999")
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
        assert "task not found" in data["error"]

    def test_get_task_has_all_fields(self, client):
        """Test that a retrieved task has all required fields."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
        )
        task_id = create_response.get_json()["id"]

        # Get the task
        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert "id" in data
        assert "title" in data
        assert "status" in data
        assert "created_at" in data


class TestUpdateTask:
    """Tests for PUT /tasks/{id}"""

    def test_update_task_title(self, client):
        """Test updating only a task's title."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Old title"}),
            content_type="application/json",
        )
        task_id = create_response.get_json()["id"]
        original_status = create_response.get_json()["status"]

        # Update the title
        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "New title"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "New title"
        assert data["status"] == original_status

    def test_update_task_status(self, client):
        """Test updating only a task's status."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
        )
        task_id = create_response.get_json()["id"]
        original_title = create_response.get_json()["title"]

        # Update the status
        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == original_title
        assert data["status"] == "completed"

    def test_update_task_title_and_status(self, client):
        """Test updating both title and status."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Old title"}),
            content_type="application/json",
        )
        task_id = create_response.get_json()["id"]

        # Update both
        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "New title", "status": "in_progress"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "New title"
        assert data["status"] == "in_progress"

    def test_update_task_not_found(self, client):
        """Test updating a non-existent task returns 404."""
        response = client.put(
            "/tasks/999",
            data=json.dumps({"title": "New title"}),
            content_type="application/json",
        )
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
        assert "task not found" in data["error"]

    def test_update_task_empty_title(self, client):
        """Test updating with an empty title returns 400."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
        )
        task_id = create_response.get_json()["id"]

        # Try to update with empty title
        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": ""}),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_update_task_whitespace_only_title(self, client):
        """Test updating with whitespace-only title returns 400."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
        )
        task_id = create_response.get_json()["id"]

        # Try to update with whitespace-only title
        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "   "}),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_update_task_preserves_created_at(self, client):
        """Test that updating a task preserves its created_at."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
        )
        task_id = create_response.get_json()["id"]
        original_created_at = create_response.get_json()["created_at"]

        # Update the task
        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "Updated title"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["created_at"] == original_created_at


class TestHealth:
    """Tests for GET /health"""

    def test_health_check(self, client):
        """Test the health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_create_list_get_update_workflow(self, client):
        """Test a complete workflow of creating, listing, getting, and updating."""
        # Create task 1
        create_response_1 = client.post(
            "/tasks",
            data=json.dumps({"title": "Task 1"}),
            content_type="application/json",
        )
        task_id_1 = create_response_1.get_json()["id"]

        # Create task 2
        create_response_2 = client.post(
            "/tasks",
            data=json.dumps({"title": "Task 2"}),
            content_type="application/json",
        )
        task_id_2 = create_response_2.get_json()["id"]

        # List all tasks
        list_response = client.get("/tasks")
        assert list_response.status_code == 200
        tasks = list_response.get_json()
        assert len(tasks) == 2

        # Get first task
        get_response = client.get(f"/tasks/{task_id_1}")
        assert get_response.status_code == 200
        task = get_response.get_json()
        assert task["title"] == "Task 1"

        # Update first task
        update_response = client.put(
            f"/tasks/{task_id_1}",
            data=json.dumps({"title": "Updated Task 1", "status": "completed"}),
            content_type="application/json",
        )
        assert update_response.status_code == 200
        updated_task = update_response.get_json()
        assert updated_task["title"] == "Updated Task 1"
        assert updated_task["status"] == "completed"

        # Verify update persisted
        get_response_2 = client.get(f"/tasks/{task_id_1}")
        assert get_response_2.status_code == 200
        verified_task = get_response_2.get_json()
        assert verified_task["title"] == "Updated Task 1"
        assert verified_task["status"] == "completed"
