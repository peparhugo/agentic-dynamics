"""
Tests for the Flask Task Management API
"""

import pytest
import json
import os
import tempfile
from datetime import datetime
from unittest.mock import patch, MagicMock
import app as app_module
from tasks_celery import celery_app


@pytest.fixture
def client():
    """Create a test client and initialize a fresh database."""
    # Create a temporary database file
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    # Set the database to the test database
    app_module.DATABASE = db_path

    # Configure Celery for testing (synchronous execution)
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )

    # Initialize app with test database
    with app_module.app.app_context():
        app_module.init_db()

    test_client = app_module.app.test_client()
    yield test_client

    # Clean up the test database
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def auth_user(client):
    """Register and return a user with a valid JWT token."""
    response = client.post(
        "/auth/register",
        data=json.dumps({
            "username": "testuser",
            "password": "password123",
            "email": "testuser@example.com"
        }),
        content_type="application/json",
    )
    assert response.status_code == 201
    token = response.get_json()["token"]
    return {
        "username": "testuser",
        "email": "testuser@example.com",
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"}
    }


class TestAuth:
    """Tests for authentication endpoints"""

    def test_register_success(self, client):
        """Test successful user registration."""
        response = client.post(
            "/auth/register",
            data=json.dumps({"username": "newuser", "password": "password123"}),
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.get_json()
        assert "token" in data
        assert data["token"] is not None

    def test_register_missing_username(self, client):
        """Test registration without username returns 400."""
        response = client.post(
            "/auth/register",
            data=json.dumps({"password": "password123"}),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_register_missing_password(self, client):
        """Test registration without password returns 400."""
        response = client.post(
            "/auth/register",
            data=json.dumps({"username": "newuser"}),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_register_short_password(self, client):
        """Test registration with short password returns 400."""
        response = client.post(
            "/auth/register",
            data=json.dumps({"username": "newuser", "password": "short"}),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "at least 6 characters" in data["error"]

    def test_register_duplicate_username(self, client):
        """Test registration with duplicate username returns 400."""
        # Register first user
        client.post(
            "/auth/register",
            data=json.dumps({"username": "testuser", "password": "password123"}),
            content_type="application/json",
        )

        # Try to register with same username
        response = client.post(
            "/auth/register",
            data=json.dumps({"username": "testuser", "password": "different123"}),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "already exists" in data["error"]

    def test_login_success(self, client, auth_user):
        """Test successful login returns a token."""
        response = client.post(
            "/auth/login",
            data=json.dumps({"username": "testuser", "password": "password123"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "token" in data
        assert data["token"] is not None

    def test_login_invalid_username(self, client):
        """Test login with invalid username returns 401."""
        response = client.post(
            "/auth/login",
            data=json.dumps({"username": "nonexistent", "password": "password123"}),
            content_type="application/json",
        )
        assert response.status_code == 401
        data = response.get_json()
        assert "invalid credentials" in data["error"]

    def test_login_invalid_password(self, client, auth_user):
        """Test login with invalid password returns 401."""
        response = client.post(
            "/auth/login",
            data=json.dumps({"username": "testuser", "password": "wrongpassword"}),
            content_type="application/json",
        )
        assert response.status_code == 401
        data = response.get_json()
        assert "invalid credentials" in data["error"]

    def test_login_missing_credentials(self, client):
        """Test login without credentials returns 400."""
        response = client.post(
            "/auth/login",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data


class TestCreateTask:
    """Tests for POST /tasks"""

    def test_create_task_success(self, client, auth_user):
        """Test creating a task with a valid title."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "Buy groceries"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert data["id"] is not None
        assert data["created_at"] is not None

    def test_create_task_missing_auth(self, client):
        """Test creating a task without auth returns 401."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "Buy groceries"}),
            content_type="application/json",
        )
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_create_task_invalid_token(self, client):
        """Test creating a task with invalid token returns 401."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "Buy groceries"}),
            content_type="application/json",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_create_task_missing_title(self, client, auth_user):
        """Test creating a task without a title returns 400."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": ""}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "title is required" in data["error"]

    def test_create_task_no_title_field(self, client, auth_user):
        """Test creating a task with no title field returns 400."""
        response = client.post(
            "/tasks",
            data=json.dumps({}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_create_task_only_whitespace(self, client, auth_user):
        """Test creating a task with only whitespace title returns 400."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "   "}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_create_task_default_status(self, client, auth_user):
        """Test that created tasks default to 'pending' status."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["status"] == "pending"

    def test_create_task_with_special_characters(self, client, auth_user):
        """Test creating a task with special characters."""
        title = "Test with special chars: !@#$%^&*()"
        response = client.post(
            "/tasks",
            data=json.dumps({"title": title}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == title


class TestListTasks:
    """Tests for GET /tasks"""

    def test_list_tasks_empty(self, client, auth_user):
        """Test listing tasks when database is empty."""
        response = client.get("/tasks", headers=auth_user["headers"])
        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_list_tasks_missing_auth(self, client):
        """Test listing tasks without auth returns 401."""
        response = client.get("/tasks")
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_list_tasks_single(self, client, auth_user):
        """Test listing a single task."""
        # Create a task
        client.post(
            "/tasks",
            data=json.dumps({"title": "Task 1"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )

        # List tasks
        response = client.get("/tasks", headers=auth_user["headers"])
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "Task 1"

    def test_list_tasks_multiple_ordered_by_created_at_desc(self, client, auth_user):
        """Test that tasks are ordered by created_at descending."""
        # Create multiple tasks
        for i in range(3):
            client.post(
                "/tasks",
                data=json.dumps({"title": f"Task {i+1}"}),
                content_type="application/json",
                headers=auth_user["headers"],
            )

        # List tasks
        response = client.get("/tasks", headers=auth_user["headers"])
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 3

        # Verify they're ordered by created_at descending (most recent first)
        for i in range(len(data) - 1):
            assert data[i]["created_at"] >= data[i + 1]["created_at"]

    def test_list_tasks_has_required_fields(self, client, auth_user):
        """Test that each task has all required fields."""
        # Create a task
        client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )

        # List tasks
        response = client.get("/tasks", headers=auth_user["headers"])
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        task = data[0]
        assert "id" in task
        assert "title" in task
        assert "status" in task
        assert "created_at" in task

    def test_list_tasks_only_own_tasks(self, client):
        """Test that users only see their own tasks."""
        # Register first user
        response1 = client.post(
            "/auth/register",
            data=json.dumps({"username": "user1", "password": "password123"}),
            content_type="application/json",
        )
        token1 = response1.get_json()["token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        # Register second user
        response2 = client.post(
            "/auth/register",
            data=json.dumps({"username": "user2", "password": "password123"}),
            content_type="application/json",
        )
        token2 = response2.get_json()["token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # User 1 creates a task
        client.post(
            "/tasks",
            data=json.dumps({"title": "User 1 Task"}),
            content_type="application/json",
            headers=headers1,
        )

        # User 2 creates a task
        client.post(
            "/tasks",
            data=json.dumps({"title": "User 2 Task"}),
            content_type="application/json",
            headers=headers2,
        )

        # User 1 lists tasks - should only see their own
        response = client.get("/tasks", headers=headers1)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "User 1 Task"

        # User 2 lists tasks - should only see their own
        response = client.get("/tasks", headers=headers2)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "User 2 Task"


class TestGetTask:
    """Tests for GET /tasks/{id}"""

    def test_get_task_success(self, client, auth_user):
        """Test getting a task by ID."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        task_id = create_response.get_json()["id"]

        # Get the task
        response = client.get(f"/tasks/{task_id}", headers=auth_user["headers"])
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Test task"
        assert data["status"] == "pending"

    def test_get_task_missing_auth(self, client):
        """Test getting a task without auth returns 401."""
        response = client.get("/tasks/999")
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_get_task_not_found(self, client, auth_user):
        """Test getting a non-existent task returns 404."""
        response = client.get("/tasks/999", headers=auth_user["headers"])
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
        assert "task not found" in data["error"]

    def test_get_task_not_owned_by_user(self, client):
        """Test getting a task owned by another user returns 404."""
        # Register first user
        response1 = client.post(
            "/auth/register",
            data=json.dumps({"username": "user1", "password": "password123"}),
            content_type="application/json",
        )
        token1 = response1.get_json()["token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        # Register second user
        response2 = client.post(
            "/auth/register",
            data=json.dumps({"username": "user2", "password": "password123"}),
            content_type="application/json",
        )
        token2 = response2.get_json()["token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # User 1 creates a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "User 1 Task"}),
            content_type="application/json",
            headers=headers1,
        )
        task_id = create_response.get_json()["id"]

        # User 2 tries to get User 1's task - should return 404
        response = client.get(f"/tasks/{task_id}", headers=headers2)
        assert response.status_code == 404

    def test_get_task_has_all_fields(self, client, auth_user):
        """Test that a retrieved task has all required fields."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        task_id = create_response.get_json()["id"]

        # Get the task
        response = client.get(f"/tasks/{task_id}", headers=auth_user["headers"])
        assert response.status_code == 200
        data = response.get_json()
        assert "id" in data
        assert "title" in data
        assert "status" in data
        assert "created_at" in data


class TestUpdateTask:
    """Tests for PUT /tasks/{id}"""

    def test_update_task_title(self, client, auth_user):
        """Test updating only a task's title."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Old title"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        task_id = create_response.get_json()["id"]
        original_status = create_response.get_json()["status"]

        # Update the title
        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "New title"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "New title"
        assert data["status"] == original_status

    def test_update_task_missing_auth(self, client):
        """Test updating a task without auth returns 401."""
        response = client.put(
            "/tasks/999",
            data=json.dumps({"title": "New title"}),
            content_type="application/json",
        )
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_update_task_status(self, client, auth_user):
        """Test updating only a task's status."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        task_id = create_response.get_json()["id"]
        original_title = create_response.get_json()["title"]

        # Update the status
        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == original_title
        assert data["status"] == "completed"

    def test_update_task_title_and_status(self, client, auth_user):
        """Test updating both title and status."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Old title"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        task_id = create_response.get_json()["id"]

        # Update both
        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "New title", "status": "in_progress"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "New title"
        assert data["status"] == "in_progress"

    def test_update_task_not_found(self, client, auth_user):
        """Test updating a non-existent task returns 404."""
        response = client.put(
            "/tasks/999",
            data=json.dumps({"title": "New title"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
        assert "task not found" in data["error"]

    def test_update_task_not_owned_by_user(self, client):
        """Test updating a task owned by another user returns 404."""
        # Register first user
        response1 = client.post(
            "/auth/register",
            data=json.dumps({"username": "user1", "password": "password123"}),
            content_type="application/json",
        )
        token1 = response1.get_json()["token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        # Register second user
        response2 = client.post(
            "/auth/register",
            data=json.dumps({"username": "user2", "password": "password123"}),
            content_type="application/json",
        )
        token2 = response2.get_json()["token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # User 1 creates a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "User 1 Task"}),
            content_type="application/json",
            headers=headers1,
        )
        task_id = create_response.get_json()["id"]

        # User 2 tries to update User 1's task - should return 404
        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "Hacked"}),
            content_type="application/json",
            headers=headers2,
        )
        assert response.status_code == 404

    def test_update_task_empty_title(self, client, auth_user):
        """Test updating with an empty title returns 400."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        task_id = create_response.get_json()["id"]

        # Try to update with empty title
        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": ""}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_update_task_whitespace_only_title(self, client, auth_user):
        """Test updating with whitespace-only title returns 400."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        task_id = create_response.get_json()["id"]

        # Try to update with whitespace-only title
        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "   "}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_update_task_preserves_created_at(self, client, auth_user):
        """Test that updating a task preserves its created_at."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        task_id = create_response.get_json()["id"]
        original_created_at = create_response.get_json()["created_at"]

        # Update the task
        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "Updated title"}),
            content_type="application/json",
            headers=auth_user["headers"],
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

    def test_create_list_get_update_workflow(self, client, auth_user):
        """Test a complete workflow of creating, listing, getting, and updating."""
        # Create task 1
        create_response_1 = client.post(
            "/tasks",
            data=json.dumps({"title": "Task 1"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        task_id_1 = create_response_1.get_json()["id"]

        # Create task 2
        create_response_2 = client.post(
            "/tasks",
            data=json.dumps({"title": "Task 2"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        task_id_2 = create_response_2.get_json()["id"]

        # List all tasks
        list_response = client.get("/tasks", headers=auth_user["headers"])
        assert list_response.status_code == 200
        tasks = list_response.get_json()
        assert len(tasks) == 2

        # Get first task
        get_response = client.get(f"/tasks/{task_id_1}", headers=auth_user["headers"])
        assert get_response.status_code == 200
        task = get_response.get_json()
        assert task["title"] == "Task 1"

        # Update first task
        update_response = client.put(
            f"/tasks/{task_id_1}",
            data=json.dumps({"title": "Updated Task 1", "status": "completed"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert update_response.status_code == 200
        updated_task = update_response.get_json()
        assert updated_task["title"] == "Updated Task 1"
        assert updated_task["status"] == "completed"

        # Verify update persisted
        get_response_2 = client.get(f"/tasks/{task_id_1}", headers=auth_user["headers"])
        assert get_response_2.status_code == 200
        verified_task = get_response_2.get_json()
        assert verified_task["title"] == "Updated Task 1"
        assert verified_task["status"] == "completed"


class TestNotificationTrigger:
    """Tests for the email notification trigger logic."""

    def test_notification_triggered_on_completion(self, client, auth_user):
        """Test that a notification is triggered when status changes to 'completed'."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Important Task"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        task_id = create_response.get_json()["id"]

        # Mock the send_notification_email task
        with patch("app.send_notification_email") as mock_task:
            # Update task to completed
            response = client.put(
                f"/tasks/{task_id}",
                data=json.dumps({"status": "completed"}),
                content_type="application/json",
                headers=auth_user["headers"],
            )
            assert response.status_code == 200

            # Verify the task was triggered
            mock_task.delay.assert_called_once_with(
                "testuser@example.com",
                "Important Task"
            )

    def test_notification_not_triggered_without_email(self, client):
        """Test that a notification is not triggered if user has no email."""
        # Register user without email
        register_response = client.post(
            "/auth/register",
            data=json.dumps({
                "username": "noemaul",
                "password": "password123"
            }),
            content_type="application/json",
        )
        token = register_response.get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Task without email"}),
            content_type="application/json",
            headers=headers,
        )
        task_id = create_response.get_json()["id"]

        # Mock the send_notification_email task
        with patch("app.send_notification_email") as mock_task:
            # Update task to completed
            response = client.put(
                f"/tasks/{task_id}",
                data=json.dumps({"status": "completed"}),
                content_type="application/json",
                headers=headers,
            )
            assert response.status_code == 200

            # Verify the task was NOT triggered (because user has no email)
            mock_task.delay.assert_not_called()

    def test_notification_not_triggered_for_other_status_changes(self, client, auth_user):
        """Test that a notification is not triggered for non-completed status changes."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test Task"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        task_id = create_response.get_json()["id"]

        # Mock the send_notification_email task
        with patch("app.send_notification_email") as mock_task:
            # Update task to in_progress
            response = client.put(
                f"/tasks/{task_id}",
                data=json.dumps({"status": "in_progress"}),
                content_type="application/json",
                headers=auth_user["headers"],
            )
            assert response.status_code == 200

            # Verify the task was NOT triggered
            mock_task.delay.assert_not_called()

    def test_notification_only_on_transition_to_completed(self, client, auth_user):
        """Test that a notification is only triggered when transitioning TO completed."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test Task"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        task_id = create_response.get_json()["id"]

        # Mock the send_notification_email task
        with patch("app.send_notification_email") as mock_task:
            # First update: pending -> completed (should trigger)
            response1 = client.put(
                f"/tasks/{task_id}",
                data=json.dumps({"status": "completed"}),
                content_type="application/json",
                headers=auth_user["headers"],
            )
            assert response1.status_code == 200
            assert mock_task.delay.call_count == 1

            # Reset mock
            mock_task.reset_mock()

            # Second update: completed -> completed (should NOT trigger)
            response2 = client.put(
                f"/tasks/{task_id}",
                data=json.dumps({"status": "completed"}),
                content_type="application/json",
                headers=auth_user["headers"],
            )
            assert response2.status_code == 200
            mock_task.delay.assert_not_called()

    def test_notification_with_title_change_and_completion(self, client, auth_user):
        """Test that notification is triggered when updating title and status to completed."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Old Title"}),
            content_type="application/json",
            headers=auth_user["headers"],
        )
        task_id = create_response.get_json()["id"]

        # Mock the send_notification_email task
        with patch("app.send_notification_email") as mock_task:
            # Update both title and status to completed
            response = client.put(
                f"/tasks/{task_id}",
                data=json.dumps({"title": "New Title", "status": "completed"}),
                content_type="application/json",
                headers=auth_user["headers"],
            )
            assert response.status_code == 200

            # Verify the task was triggered with the NEW title
            mock_task.delay.assert_called_once_with(
                "testuser@example.com",
                "New Title"
            )
