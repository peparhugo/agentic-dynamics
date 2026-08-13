"""
Tests for the Task Management API
"""

import pytest
import json
import os
import sqlite3
import app as app_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create test client with isolated database."""
    test_db = str(tmp_path / "test_tasks.db")
    monkeypatch.setenv("DATABASE", test_db)
    monkeypatch.setattr(app_module, "DATABASE", test_db)

    app = app_module.app
    app.config["TESTING"] = True

    with app.app_context():
        app_module.init_db()

    yield app.test_client()


class TestCreateTask:
    """Tests for POST /tasks"""

    def test_create_task_success(self, client):
        """Create a task with valid title."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "Buy groceries"}),
            content_type="application/json"
        )
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert data["id"] is not None
        assert data["created_at"] is not None

    def test_create_task_missing_title(self, client):
        """Return 400 when title is missing."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": ""}),
            content_type="application/json"
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] == "title is required"

    def test_create_task_no_json(self, client):
        """Return 400 when no JSON body."""
        response = client.post(
            "/tasks",
            data=json.dumps({}),
            content_type="application/json"
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] == "title is required"

    def test_create_task_whitespace_only(self, client):
        """Return 400 when title is whitespace only."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "   "}),
            content_type="application/json"
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] == "title is required"


class TestListTasks:
    """Tests for GET /tasks"""

    def test_list_tasks_empty(self, client):
        """List tasks returns empty array when no tasks."""
        response = client.get("/tasks")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == []

    def test_list_tasks_single(self, client):
        """List tasks returns single task."""
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

    def test_list_tasks_multiple_ordered(self, client):
        """List tasks returns multiple tasks ordered by created_at descending."""
        # Create tasks with a small delay to ensure different timestamps
        import time
        client.post(
            "/tasks",
            data=json.dumps({"title": "Task 1"}),
            content_type="application/json"
        )
        time.sleep(0.01)
        client.post(
            "/tasks",
            data=json.dumps({"title": "Task 2"}),
            content_type="application/json"
        )
        time.sleep(0.01)
        client.post(
            "/tasks",
            data=json.dumps({"title": "Task 3"}),
            content_type="application/json"
        )

        response = client.get("/tasks")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 3
        # Should be in descending order by created_at
        assert data[0]["title"] == "Task 3"
        assert data[1]["title"] == "Task 2"
        assert data[2]["title"] == "Task 1"


class TestGetTask:
    """Tests for GET /tasks/{id}"""

    def test_get_task_success(self, client):
        """Get a task by ID."""
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json"
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["id"] == task_id
        assert data["title"] == "Test task"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client):
        """Return 404 when task not found."""
        response = client.get("/tasks/999")
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["error"] == "task not found"


class TestUpdateTask:
    """Tests for PUT /tasks/{id}"""

    def test_update_task_title(self, client):
        """Update task title."""
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
        assert data["title"] == "New title"
        assert data["status"] == "pending"

    def test_update_task_status(self, client):
        """Update task status."""
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
        assert data["status"] == "completed"
        assert data["title"] == "Test task"

    def test_update_task_title_and_status(self, client):
        """Update both title and status."""
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
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_task_not_found(self, client):
        """Return 404 when updating non-existent task."""
        response = client.put(
            "/tasks/999",
            data=json.dumps({"title": "New title"}),
            content_type="application/json"
        )
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["error"] == "task not found"

    def test_update_task_empty_title(self, client):
        """Empty title is treated as removing the value - should use current."""
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Original"}),
            content_type="application/json"
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": ""}),
            content_type="application/json"
        )
        # Empty title should keep original
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["title"] == "Original"


class TestHealthEndpoint:
    """Tests for GET /health"""

    def test_health_check(self, client):
        """Health endpoint returns ok."""
        response = client.get("/health")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "ok"
