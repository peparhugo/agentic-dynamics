"""
Tests for the Flask Task Management API
"""

import pytest
import sqlite3
import os
from datetime import datetime
from task_app import app, init_db


@pytest.fixture
def client():
    """Create a test client with a fresh database"""
    import tempfile
    import shutil

    # Create a temporary directory for the test database
    test_dir = tempfile.mkdtemp()
    test_db = os.path.join(test_dir, "test_tasks.db")
    os.environ["DATABASE"] = test_db

    # Remove old test database if it exists
    if os.path.exists(test_db):
        os.remove(test_db)

    # Initialize database
    init_db()

    # Create test client
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

    # Cleanup
    shutil.rmtree(test_dir, ignore_errors=True)


class TestCreateTask:
    def test_create_task_success(self, client):
        """Test creating a task with valid title"""
        response = client.post("/tasks", json={"title": "Buy groceries"})
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert data["id"] == 1  # First task should have id 1
        assert "created_at" in data

    def test_create_task_missing_title(self, client):
        """Test creating a task without title"""
        response = client.post("/tasks", json={})
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert data["error"] == "title is required"

    def test_create_task_empty_title(self, client):
        """Test creating a task with empty title"""
        response = client.post("/tasks", json={"title": ""})
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_create_task_whitespace_title(self, client):
        """Test creating a task with whitespace-only title"""
        response = client.post("/tasks", json={"title": "   "})
        assert response.status_code == 400

    def test_create_task_no_json(self, client):
        """Test creating a task with no JSON body"""
        response = client.post("/tasks")
        assert response.status_code == 400

    def test_create_multiple_tasks(self, client):
        """Test creating multiple tasks"""
        response1 = client.post("/tasks", json={"title": "Task 1"})
        assert response1.status_code == 201
        task1 = response1.get_json()
        assert task1["id"] == 1

        response2 = client.post("/tasks", json={"title": "Task 2"})
        assert response2.status_code == 201
        task2 = response2.get_json()
        assert task2["id"] == 2

        response3 = client.post("/tasks", json={"title": "Task 3"})
        assert response3.status_code == 201
        task3 = response3.get_json()
        assert task3["id"] == 3


class TestListTasks:
    def test_list_tasks_empty(self, client):
        """Test listing tasks when none exist"""
        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_list_tasks_ordered_by_created_at_desc(self, client):
        """Test that tasks are listed in descending order by created_at"""
        # Create three tasks
        client.post("/tasks", json={"title": "Task 1"})
        client.post("/tasks", json={"title": "Task 2"})
        client.post("/tasks", json={"title": "Task 3"})

        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 3

        # Should be in reverse order (most recent first)
        assert data[0]["title"] == "Task 3"
        assert data[1]["title"] == "Task 2"
        assert data[2]["title"] == "Task 1"

    def test_list_tasks_returns_all_fields(self, client):
        """Test that list endpoint returns all required fields"""
        client.post("/tasks", json={"title": "Test Task"})

        response = client.get("/tasks")
        data = response.get_json()
        task = data[0]

        assert "id" in task
        assert "title" in task
        assert "status" in task
        assert "created_at" in task


class TestGetTask:
    def test_get_task_success(self, client):
        """Test getting a single task by id"""
        create_response = client.post("/tasks", json={"title": "Buy milk"})
        task_id = create_response.get_json()["id"]

        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Buy milk"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client):
        """Test getting a task that doesn't exist"""
        response = client.get("/tasks/999")
        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "task not found"

    def test_get_task_first_id(self, client):
        """Test getting the first task (id 1)"""
        create_response = client.post("/tasks", json={"title": "First task"})
        task = create_response.get_json()

        response = client.get(f"/tasks/{task['id']}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "First task"
        assert data["id"] == 1


class TestUpdateTask:
    def test_update_task_title(self, client):
        """Test updating a task's title"""
        create_response = client.post("/tasks", json={"title": "Old title"})
        task_id = create_response.get_json()["id"]

        response = client.put(f"/tasks/{task_id}", json={"title": "New title"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "New title"
        assert data["status"] == "pending"
        assert data["id"] == task_id

    def test_update_task_status(self, client):
        """Test updating a task's status"""
        create_response = client.post("/tasks", json={"title": "Test"})
        task_id = create_response.get_json()["id"]

        response = client.put(f"/tasks/{task_id}", json={"status": "completed"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "completed"
        assert data["title"] == "Test"

    def test_update_task_title_and_status(self, client):
        """Test updating both title and status"""
        create_response = client.post("/tasks", json={"title": "Original"})
        task_id = create_response.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated", "status": "in_progress"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_task_not_found(self, client):
        """Test updating a task that doesn't exist"""
        response = client.put("/tasks/999", json={"title": "New title"})
        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "task not found"

    def test_update_task_no_changes(self, client):
        """Test updating a task with no changes (empty JSON)"""
        create_response = client.post("/tasks", json={"title": "Original"})
        task_id = create_response.get_json()["id"]
        original = create_response.get_json()

        response = client.put(f"/tasks/{task_id}", json={})
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == original["title"]
        assert data["status"] == original["status"]

    def test_update_task_no_json(self, client):
        """Test updating a task with no JSON body"""
        create_response = client.post("/tasks", json={"title": "Test"})
        task_id = create_response.get_json()["id"]

        response = client.put(f"/tasks/{task_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id


class TestIntegration:
    def test_full_workflow(self, client):
        """Test a complete workflow: create, list, get, update"""
        # Create tasks
        response1 = client.post("/tasks", json={"title": "Task A"})
        task1_id = response1.get_json()["id"]

        response2 = client.post("/tasks", json={"title": "Task B"})
        task2_id = response2.get_json()["id"]

        # List all tasks
        response = client.get("/tasks")
        tasks = response.get_json()
        assert len(tasks) == 2
        assert tasks[0]["title"] == "Task B"  # Most recent first
        assert tasks[1]["title"] == "Task A"

        # Get specific task
        response = client.get(f"/tasks/{task1_id}")
        task = response.get_json()
        assert task["title"] == "Task A"
        assert task["status"] == "pending"

        # Update task
        response = client.put(
            f"/tasks/{task1_id}",
            json={"title": "Task A Updated", "status": "completed"}
        )
        task = response.get_json()
        assert task["title"] == "Task A Updated"
        assert task["status"] == "completed"

        # Verify update persisted
        response = client.get(f"/tasks/{task1_id}")
        task = response.get_json()
        assert task["title"] == "Task A Updated"
        assert task["status"] == "completed"

    def test_persistence_across_requests(self, client):
        """Test that data persists across multiple requests"""
        # Create a task
        response = client.post("/tasks", json={"title": "Persistent"})
        task_id = response.get_json()["id"]
        created_at = response.get_json()["created_at"]

        # Get it multiple times
        for _ in range(3):
            response = client.get(f"/tasks/{task_id}")
            data = response.get_json()
            assert data["id"] == task_id
            assert data["title"] == "Persistent"
            assert data["created_at"] == created_at

    def test_status_values(self, client):
        """Test various status values"""
        response = client.post("/tasks", json={"title": "Task"})
        task_id = response.get_json()["id"]

        statuses = ["pending", "in_progress", "completed", "archived"]
        for status in statuses:
            response = client.put(f"/tasks/{task_id}", json={"status": status})
            data = response.get_json()
            assert data["status"] == status

    def test_task_creation_timestamps(self, client):
        """Test that tasks have valid ISO format timestamps"""
        response = client.post("/tasks", json={"title": "Task"})
        data = response.get_json()

        # Should be valid ISO format
        created_at = data["created_at"]
        assert "T" in created_at  # ISO format includes T
        assert "-" in created_at  # Has date separators

        # Should parse as datetime
        datetime.fromisoformat(created_at)


class TestErrorHandling:
    def test_invalid_json(self, client):
        """Test sending invalid JSON"""
        response = client.post(
            "/tasks",
            data="invalid json",
            content_type="application/json"
        )
        # Flask handles this gracefully
        assert response.status_code in [400, 415]

    def test_null_title(self, client):
        """Test creating a task with null title"""
        response = client.post("/tasks", json={"title": None})
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "title is required"

    def test_numeric_title(self, client):
        """Test creating a task with numeric title (should be converted to string)"""
        response = client.post("/tasks", json={"title": 123})
        # Should work - converted to string
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "123"


class TestHealth:
    def test_health_endpoint(self, client):
        """Test the health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
