"""
Tests for the Flask task management API.
"""

import pytest
import json
import os
import sqlite3
from datetime import datetime
from app import app, init_db, get_db

# Use a test database
TEST_DB = "test_tasks.db"


@pytest.fixture
def client():
    """Create a test client with a temporary database."""
    # Clean up any existing test database
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    os.environ["DATABASE"] = TEST_DB

    # Initialize the database for tests
    init_db()

    client = app.test_client()

    yield client

    # Clean up the test database after each test
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def clear_tasks():
    """Clear all tasks from the database."""
    with get_db() as conn:
        conn.execute("DELETE FROM tasks")
        conn.commit()


class TestTaskCreation:
    """Tests for POST /tasks endpoint."""

    def test_create_task_success(self, client):
        """Test creating a task with valid title."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "Learn Flask"}),
            content_type="application/json"
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["title"] == "Learn Flask"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data

    def test_create_task_missing_title(self, client):
        """Test creating a task without title returns 400."""
        response = client.post(
            "/tasks",
            data=json.dumps({}),
            content_type="application/json"
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
        assert data["error"] == "title is required"

    def test_create_task_empty_title(self, client):
        """Test creating a task with empty title returns 400."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": ""}),
            content_type="application/json"
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] == "title is required"

    def test_create_task_whitespace_title(self, client):
        """Test creating a task with whitespace-only title returns 400."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "   "}),
            content_type="application/json"
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] == "title is required"

    def test_create_task_no_json(self, client):
        """Test creating a task with no JSON body returns 400."""
        response = client.post("/tasks")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] == "title is required"


class TestTaskListing:
    """Tests for GET /tasks endpoint."""

    def test_list_empty_tasks(self, client):
        """Test listing tasks when none exist."""
        response = client.get("/tasks")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == []

    def test_list_single_task(self, client):
        """Test listing a single task."""
        # Create a task
        client.post(
            "/tasks",
            data=json.dumps({"title": "Task 1"}),
            content_type="application/json"
        )

        response = client.get("/tasks")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 1
        assert data[0]["title"] == "Task 1"

    def test_list_multiple_tasks_ordered_by_created_at_desc(self, client):
        """Test listing multiple tasks ordered by created_at descending."""
        # Create multiple tasks
        for i in range(1, 4):
            client.post(
                "/tasks",
                data=json.dumps({"title": f"Task {i}"}),
                content_type="application/json"
            )

        response = client.get("/tasks")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 3

        # Verify ordering - most recent first
        assert data[0]["title"] == "Task 3"
        assert data[1]["title"] == "Task 2"
        assert data[2]["title"] == "Task 1"

        # Verify all have valid created_at timestamps
        for task in data:
            assert task["created_at"] is not None


class TestTaskRetrieval:
    """Tests for GET /tasks/{id} endpoint."""

    def test_get_task_success(self, client):
        """Test retrieving an existing task."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Buy groceries"}),
            content_type="application/json"
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.get(f"/tasks/{task_id}")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["id"] == task_id
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client):
        """Test retrieving a non-existent task returns 404."""
        response = client.get("/tasks/999")

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["error"] == "task not found"


class TestTaskUpdate:
    """Tests for PUT /tasks/{id} endpoint."""

    def test_update_task_title(self, client):
        """Test updating only the title."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Old title"}),
            content_type="application/json"
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "New title"}),
            content_type="application/json"
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["id"] == task_id
        assert data["title"] == "New title"
        assert data["status"] == "pending"

    def test_update_task_status(self, client):
        """Test updating only the status."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json"
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json"
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["id"] == task_id
        assert data["title"] == "Test task"
        assert data["status"] == "completed"

    def test_update_task_title_and_status(self, client):
        """Test updating both title and status."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Original"}),
            content_type="application/json"
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "Updated", "status": "in_progress"}),
            content_type="application/json"
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["id"] == task_id
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_task_not_found(self, client):
        """Test updating a non-existent task returns 404."""
        response = client.put(
            "/tasks/999",
            data=json.dumps({"title": "Should fail"}),
            content_type="application/json"
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["error"] == "task not found"

    def test_update_task_empty_body(self, client):
        """Test updating a task with empty body (no changes)."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Original"}),
            content_type="application/json"
        )
        task_id = json.loads(create_response.data)["id"]
        original_created_at = json.loads(create_response.data)["created_at"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({}),
            content_type="application/json"
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["id"] == task_id
        assert data["title"] == "Original"
        assert data["created_at"] == original_created_at


class TestTaskInitialization:
    """Tests for database initialization."""

    def test_db_schema_exists(self, client):
        """Test that database schema is created on startup."""
        # Try to create and retrieve a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Schema test"}),
            content_type="application/json"
        )

        assert create_response.status_code == 201

        # Verify schema by checking we can query the table
        response = client.get("/tasks")
        assert response.status_code == 200
