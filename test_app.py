"""
Comprehensive tests for the Flask task management API.
"""

import pytest
import os
import json
from app import app, init_db, DATABASE
import tempfile


@pytest.fixture
def client():
    """Create a test client with a temporary database."""
    # Use a temporary database for testing
    db_fd, db_path = tempfile.mkstemp()

    # Patch the app module's DATABASE variable
    import app as app_module
    original_db = app_module.DATABASE
    app_module.DATABASE = db_path

    app.config["TESTING"] = True

    with app.app_context():
        init_db()

    with app.test_client() as client:
        yield client

    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)
    app_module.DATABASE = original_db


class TestCreateTask:
    def test_create_task_success(self, client):
        """Test successfully creating a task."""
        response = client.post(
            "/tasks",
            json={"title": "Test task"},
            content_type="application/json"
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Test task"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data

    def test_create_task_missing_title(self, client):
        """Test creating a task without a title returns 400."""
        response = client.post(
            "/tasks",
            json={},
            content_type="application/json"
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_create_task_empty_title(self, client):
        """Test creating a task with empty title returns 400."""
        response = client.post(
            "/tasks",
            json={"title": "   "},
            content_type="application/json"
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_create_task_no_json(self, client):
        """Test POST with no JSON body."""
        response = client.post("/tasks")
        assert response.status_code == 400

    def test_create_task_status_default_pending(self, client):
        """Test that created task has status 'pending' by default."""
        response = client.post(
            "/tasks",
            json={"title": "New task"},
            content_type="application/json"
        )
        data = response.get_json()
        assert data["status"] == "pending"


class TestListTasks:
    def test_list_empty(self, client):
        """Test listing tasks when none exist."""
        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_list_tasks_ordered_by_created_at_desc(self, client):
        """Test that tasks are returned in reverse chronological order."""
        # Create multiple tasks
        client.post("/tasks", json={"title": "First"}, content_type="application/json")
        client.post("/tasks", json={"title": "Second"}, content_type="application/json")
        client.post("/tasks", json={"title": "Third"}, content_type="application/json")

        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.get_json()

        assert len(data) == 3
        # Should be in reverse order (newest first)
        assert data[0]["title"] == "Third"
        assert data[1]["title"] == "Second"
        assert data[2]["title"] == "First"

    def test_list_tasks_with_multiple_statuses(self, client):
        """Test listing tasks with different statuses."""
        # Create tasks
        resp1 = client.post("/tasks", json={"title": "Task 1"}, content_type="application/json")
        task1_id = resp1.get_json()["id"]

        resp2 = client.post("/tasks", json={"title": "Task 2"}, content_type="application/json")
        task2_id = resp2.get_json()["id"]

        # Update one task's status
        client.put(
            f"/tasks/{task1_id}",
            json={"status": "completed"},
            content_type="application/json"
        )

        # List and verify both tasks are there with correct statuses
        response = client.get("/tasks")
        data = response.get_json()
        assert len(data) == 2

        statuses = {t["id"]: t["status"] for t in data}
        assert statuses[task1_id] == "completed"
        assert statuses[task2_id] == "pending"


class TestGetTask:
    def test_get_task_success(self, client):
        """Test retrieving a single task."""
        create_resp = client.post(
            "/tasks",
            json={"title": "Get me"},
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Get me"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client):
        """Test retrieving a non-existent task returns 404."""
        response = client.get("/tasks/9999")
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data


class TestUpdateTask:
    def test_update_task_title(self, client):
        """Test updating task title."""
        create_resp = client.post(
            "/tasks",
            json={"title": "Original"},
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated"},
            content_type="application/json"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "pending"  # Status should remain unchanged

    def test_update_task_status(self, client):
        """Test updating task status."""
        create_resp = client.post(
            "/tasks",
            json={"title": "Task"},
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
        assert data["status"] == "completed"
        assert data["title"] == "Task"  # Title should remain unchanged

    def test_update_task_title_and_status(self, client):
        """Test updating both title and status."""
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
        """Test updating a non-existent task returns 404."""
        response = client.put(
            "/tasks/9999",
            json={"title": "New title"},
            content_type="application/json"
        )
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_update_task_empty_body(self, client):
        """Test updating with empty body (no changes)."""
        create_resp = client.post(
            "/tasks",
            json={"title": "Original"},
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]
        original = create_resp.get_json()

        response = client.put(
            f"/tasks/{task_id}",
            json={},
            content_type="application/json"
        )
        assert response.status_code == 200
        data = response.get_json()
        # Task should be unchanged
        assert data["title"] == original["title"]
        assert data["status"] == original["status"]


class TestErrorHandling:
    def test_404_task_not_found_message(self, client):
        """Test 404 error has proper message."""
        response = client.get("/tasks/9999")
        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "task not found"

    def test_400_missing_title_message(self, client):
        """Test 400 error has proper message."""
        response = client.post(
            "/tasks",
            json={},
            content_type="application/json"
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "title is required"

    def test_responses_are_json(self, client):
        """Test all responses are JSON."""
        # GET /tasks
        response = client.get("/tasks")
        assert response.content_type == "application/json"

        # POST /tasks
        response = client.post(
            "/tasks",
            json={"title": "Test"},
            content_type="application/json"
        )
        assert response.content_type == "application/json"

        # GET /tasks/{id}
        task_id = response.get_json()["id"]
        response = client.get(f"/tasks/{task_id}")
        assert response.content_type == "application/json"

        # PUT /tasks/{id}
        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated"},
            content_type="application/json"
        )
        assert response.content_type == "application/json"

        # 404 error
        response = client.get("/tasks/9999")
        assert response.content_type == "application/json"


class TestEdgeCases:
    def test_task_id_uniqueness(self, client):
        """Test that each task has a unique ID."""
        resp1 = client.post("/tasks", json={"title": "Task 1"}, content_type="application/json")
        resp2 = client.post("/tasks", json={"title": "Task 2"}, content_type="application/json")

        id1 = resp1.get_json()["id"]
        id2 = resp2.get_json()["id"]

        assert id1 != id2

    def test_update_preserves_created_at(self, client):
        """Test that updating a task doesn't change created_at."""
        create_resp = client.post(
            "/tasks",
            json={"title": "Task"},
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]
        original_created_at = create_resp.get_json()["created_at"]

        # Update the task
        client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated"},
            content_type="application/json"
        )

        # Get the task and verify created_at is unchanged
        response = client.get(f"/tasks/{task_id}")
        data = response.get_json()
        assert data["created_at"] == original_created_at

    def test_title_with_special_characters(self, client):
        """Test creating a task with special characters in title."""
        special_title = "Task with \"quotes\", 'apostrophes', <tags>, & symbols"
        response = client.post(
            "/tasks",
            json={"title": special_title},
            content_type="application/json"
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == special_title

    def test_multiple_tasks_lifecycle(self, client):
        """Test creating, reading, and updating multiple tasks."""
        # Create 3 tasks
        ids = []
        for i in range(3):
            resp = client.post(
                "/tasks",
                json={"title": f"Task {i}"},
                content_type="application/json"
            )
            ids.append(resp.get_json()["id"])

        # Update first task
        client.put(
            f"/tasks/{ids[0]}",
            json={"status": "completed"},
            content_type="application/json"
        )

        # Update second task
        client.put(
            f"/tasks/{ids[1]}",
            json={"status": "in_progress"},
            content_type="application/json"
        )

        # List all tasks and verify
        response = client.get("/tasks")
        data = response.get_json()
        assert len(data) == 3

        statuses = {t["id"]: t["status"] for t in data}
        assert statuses[ids[0]] == "completed"
        assert statuses[ids[1]] == "in_progress"
        assert statuses[ids[2]] == "pending"
