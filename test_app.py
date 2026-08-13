"""
Tests for the Flask Task Management API
"""

import pytest
import sqlite3
import os
from datetime import datetime
from app import app, init_db


@pytest.fixture(scope="function")
def client():
    """Create a test client with a separate test database"""
    test_db = "test_tasks.db"

    # Set the test database
    os.environ["DATABASE"] = test_db

    # Clean up any existing test database
    if os.path.exists(test_db):
        os.remove(test_db)

    # Initialize the test database
    init_db()

    # Create the test client
    app.config["TESTING"] = True
    test_client = app.test_client()

    yield test_client

    # Clean up after test
    if os.path.exists(test_db):
        os.remove(test_db)


class TestCreateTask:
    def test_create_task_success(self, client):
        """Test creating a task with valid title"""
        response = client.post(
            "/tasks",
            json={"title": "Test Task"},
            content_type="application/json"
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Test Task"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data

    def test_create_task_missing_title(self, client):
        """Test creating a task without title returns 400"""
        response = client.post(
            "/tasks",
            json={},
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert data["error"] == "title is required"

    def test_create_task_empty_title(self, client):
        """Test creating a task with empty title returns 400"""
        response = client.post(
            "/tasks",
            json={"title": "   "},
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_create_task_no_json(self, client):
        """Test creating a task with no JSON body returns 400"""
        response = client.post("/tasks")

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data


class TestListTasks:
    def test_list_tasks_empty(self, client):
        """Test listing tasks when database is empty"""
        response = client.get("/tasks")

        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_list_tasks_multiple(self, client):
        """Test listing multiple tasks in descending order"""
        # Create three tasks
        client.post("/tasks", json={"title": "Task 1"}, content_type="application/json")
        client.post("/tasks", json={"title": "Task 2"}, content_type="application/json")
        client.post("/tasks", json={"title": "Task 3"}, content_type="application/json")

        response = client.get("/tasks")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 3
        # Verify descending order (newest first)
        assert data[0]["title"] == "Task 3"
        assert data[1]["title"] == "Task 2"
        assert data[2]["title"] == "Task 1"

    def test_list_tasks_ordered_by_created_at(self, client):
        """Test that tasks are ordered by created_at descending"""
        resp1 = client.post("/tasks", json={"title": "First"}, content_type="application/json")
        resp2 = client.post("/tasks", json={"title": "Second"}, content_type="application/json")

        response = client.get("/tasks")
        data = response.get_json()

        # Most recent should be first
        assert data[0]["id"] == resp2.get_json()["id"]
        assert data[1]["id"] == resp1.get_json()["id"]


class TestGetTask:
    def test_get_task_success(self, client):
        """Test getting a specific task"""
        create_resp = client.post(
            "/tasks",
            json={"title": "Test Task"},
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        response = client.get(f"/tasks/{task_id}")

        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Test Task"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client):
        """Test getting a non-existent task returns 404"""
        response = client.get("/tasks/999")

        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "task not found"


class TestUpdateTask:
    def test_update_task_title(self, client):
        """Test updating only the title"""
        create_resp = client.post(
            "/tasks",
            json={"title": "Original Title"},
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated Title"},
            content_type="application/json"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated Title"
        assert data["status"] == "pending"

    def test_update_task_status(self, client):
        """Test updating only the status"""
        create_resp = client.post(
            "/tasks",
            json={"title": "Test Task"},
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"status": "completed"},
            content_type="application/json"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Test Task"
        assert data["status"] == "completed"

    def test_update_task_both(self, client):
        """Test updating both title and status"""
        create_resp = client.post(
            "/tasks",
            json={"title": "Original"},
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated", "status": "in_progress"},
            content_type="application/json"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_task_not_found(self, client):
        """Test updating a non-existent task returns 404"""
        response = client.put(
            "/tasks/999",
            json={"title": "Updated"},
            content_type="application/json"
        )

        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "task not found"

    def test_update_task_empty_title(self, client):
        """Test updating title to empty string returns 400"""
        create_resp = client.post(
            "/tasks",
            json={"title": "Original"},
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "   "},
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_update_task_no_changes(self, client):
        """Test updating a task with no fields still returns success"""
        create_resp = client.post(
            "/tasks",
            json={"title": "Original"},
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]
        original_title = create_resp.get_json()["title"]

        response = client.put(
            f"/tasks/{task_id}",
            json={},
            content_type="application/json"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == original_title


class TestIntegration:
    def test_full_workflow(self, client):
        """Test a complete task management workflow"""
        # Create tasks
        resp1 = client.post("/tasks", json={"title": "Buy groceries"}, content_type="application/json")
        resp2 = client.post("/tasks", json={"title": "Write code"}, content_type="application/json")

        task1_id = resp1.get_json()["id"]
        task2_id = resp2.get_json()["id"]

        # List tasks
        list_resp = client.get("/tasks")
        assert len(list_resp.get_json()) == 2

        # Get single task
        get_resp = client.get(f"/tasks/{task1_id}")
        assert get_resp.get_json()["title"] == "Buy groceries"

        # Update task status
        update_resp = client.put(
            f"/tasks/{task1_id}",
            json={"status": "completed"},
            content_type="application/json"
        )
        assert update_resp.get_json()["status"] == "completed"

        # Verify update persisted
        verify_resp = client.get(f"/tasks/{task1_id}")
        assert verify_resp.get_json()["status"] == "completed"
