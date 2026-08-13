"""
Tests for the Flask task management API.
"""

import pytest
import json
import os
import sqlite3
from datetime import datetime
from unittest.mock import patch, MagicMock
from app import app, init_db, get_db, limiter

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

    # Disable rate limiting for normal tests
    app.config['RATELIMIT_ENABLED'] = False
    limiter.enabled = False

    client = app.test_client()

    yield client

    # Clean up the test database after each test
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    # Re-enable rate limiting
    app.config['RATELIMIT_ENABLED'] = True
    limiter.enabled = True


@pytest.fixture
def auth_headers(client):
    """Create a user and return auth headers."""
    # Register a user
    client.post(
        "/auth/register",
        data=json.dumps({"username": "testuser", "password": "testpass"}),
        content_type="application/json"
    )

    # Login to get token
    response = client.post(
        "/auth/login",
        data=json.dumps({"username": "testuser", "password": "testpass"}),
        content_type="application/json"
    )

    token = json.loads(response.data)["token"]
    return {"Authorization": f"Bearer {token}"}


def create_user(client, username: str, password: str) -> str:
    """Helper to create a user and return the token."""
    client.post(
        "/auth/register",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json"
    )

    response = client.post(
        "/auth/login",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json"
    )

    return json.loads(response.data)["token"]


class TestAuthentication:
    """Tests for authentication endpoints."""

    def test_register_success(self, client):
        """Test successful user registration."""
        response = client.post(
            "/auth/register",
            data=json.dumps({"username": "newuser", "password": "securepass"}),
            content_type="application/json"
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["username"] == "newuser"
        assert "id" in data
        assert "password_hash" not in data

    def test_register_duplicate_username(self, client):
        """Test registering with duplicate username returns 409."""
        client.post(
            "/auth/register",
            data=json.dumps({"username": "duplicate", "password": "pass1"}),
            content_type="application/json"
        )

        response = client.post(
            "/auth/register",
            data=json.dumps({"username": "duplicate", "password": "pass2"}),
            content_type="application/json"
        )

        assert response.status_code == 409
        data = json.loads(response.data)
        assert data["error"] == "username already exists"

    def test_register_missing_username(self, client):
        """Test registering without username returns 400."""
        response = client.post(
            "/auth/register",
            data=json.dumps({"password": "pass"}),
            content_type="application/json"
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "username and password are required" in data["error"]

    def test_register_missing_password(self, client):
        """Test registering without password returns 400."""
        response = client.post(
            "/auth/register",
            data=json.dumps({"username": "user"}),
            content_type="application/json"
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "username and password are required" in data["error"]

    def test_register_empty_credentials(self, client):
        """Test registering with empty credentials returns 400."""
        response = client.post(
            "/auth/register",
            data=json.dumps({"username": "", "password": ""}),
            content_type="application/json"
        )

        assert response.status_code == 400

    def test_login_success(self, client):
        """Test successful login."""
        client.post(
            "/auth/register",
            data=json.dumps({"username": "testuser", "password": "testpass"}),
            content_type="application/json"
        )

        response = client.post(
            "/auth/login",
            data=json.dumps({"username": "testuser", "password": "testpass"}),
            content_type="application/json"
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "token" in data
        assert isinstance(data["token"], str)
        assert len(data["token"]) > 0

    def test_login_wrong_password(self, client):
        """Test login with wrong password returns 401."""
        client.post(
            "/auth/register",
            data=json.dumps({"username": "testuser", "password": "testpass"}),
            content_type="application/json"
        )

        response = client.post(
            "/auth/login",
            data=json.dumps({"username": "testuser", "password": "wrongpass"}),
            content_type="application/json"
        )

        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["error"] == "invalid username or password"

    def test_login_nonexistent_user(self, client):
        """Test login with non-existent user returns 401."""
        response = client.post(
            "/auth/login",
            data=json.dumps({"username": "nouser", "password": "pass"}),
            content_type="application/json"
        )

        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["error"] == "invalid username or password"

    def test_login_missing_credentials(self, client):
        """Test login without credentials returns 400."""
        response = client.post(
            "/auth/login",
            data=json.dumps({"username": "user"}),
            content_type="application/json"
        )

        assert response.status_code == 400


class TestTaskCreation:
    """Tests for POST /tasks endpoint."""

    def test_create_task_success(self, client, auth_headers):
        """Test creating a task with valid title."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "Learn Flask"}),
            content_type="application/json",
            headers=auth_headers
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["title"] == "Learn Flask"
        assert data["status"] == "pending"
        assert "id" in data
        assert "owner_id" in data
        assert "created_at" in data

    def test_create_task_missing_token(self, client):
        """Test creating a task without token returns 401."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "Learn Flask"}),
            content_type="application/json"
        )

        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["error"] == "missing token"

    def test_create_task_invalid_token(self, client):
        """Test creating a task with invalid token returns 401."""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "Learn Flask"}),
            content_type="application/json",
            headers=headers
        )

        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["error"] == "invalid token"

    def test_create_task_malformed_auth_header(self, client):
        """Test creating a task with malformed auth header returns 401."""
        headers = {"Authorization": "InvalidFormat"}
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "Learn Flask"}),
            content_type="application/json",
            headers=headers
        )

        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["error"] == "missing token"

    def test_create_task_missing_title(self, client, auth_headers):
        """Test creating a task without title returns 400."""
        response = client.post(
            "/tasks",
            data=json.dumps({}),
            content_type="application/json",
            headers=auth_headers
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
        assert data["error"] == "title is required"

    def test_create_task_empty_title(self, client, auth_headers):
        """Test creating a task with empty title returns 400."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": ""}),
            content_type="application/json",
            headers=auth_headers
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] == "title is required"

    def test_create_task_whitespace_title(self, client, auth_headers):
        """Test creating a task with whitespace-only title returns 400."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "   "}),
            content_type="application/json",
            headers=auth_headers
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] == "title is required"


class TestTaskListing:
    """Tests for GET /tasks endpoint."""

    def test_list_empty_tasks(self, client, auth_headers):
        """Test listing tasks when none exist."""
        response = client.get("/tasks", headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"] == []
        assert data["next_cursor"] is None
        assert data["total"] == 0

    def test_list_single_task(self, client, auth_headers):
        """Test listing a single task."""
        # Create a task
        client.post(
            "/tasks",
            data=json.dumps({"title": "Task 1"}),
            content_type="application/json",
            headers=auth_headers
        )

        response = client.get("/tasks", headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data["data"]) == 1
        assert data["data"][0]["title"] == "Task 1"

    def test_list_multiple_tasks_ordered_by_created_at_desc(self, client, auth_headers):
        """Test listing multiple tasks ordered by created_at descending."""
        # Create multiple tasks
        for i in range(1, 4):
            client.post(
                "/tasks",
                data=json.dumps({"title": f"Task {i}"}),
                content_type="application/json",
                headers=auth_headers
            )

        response = client.get("/tasks", headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data["data"]) == 3

        # Verify ordering - most recent first (by id DESC)
        assert data["data"][0]["title"] == "Task 3"
        assert data["data"][1]["title"] == "Task 2"
        assert data["data"][2]["title"] == "Task 1"

        # Verify all have valid created_at timestamps
        for task in data["data"]:
            assert task["created_at"] is not None

    def test_list_tasks_requires_token(self, client):
        """Test listing tasks without token returns 401."""
        response = client.get("/tasks")

        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["error"] == "missing token"

    def test_list_tasks_only_shows_user_tasks(self, client):
        """Test that users only see their own tasks."""
        # Create first user and task
        token1 = create_user(client, "user1", "pass1")
        headers1 = {"Authorization": f"Bearer {token1}"}

        client.post(
            "/tasks",
            data=json.dumps({"title": "User 1 Task"}),
            content_type="application/json",
            headers=headers1
        )

        # Create second user and task
        token2 = create_user(client, "user2", "pass2")
        headers2 = {"Authorization": f"Bearer {token2}"}

        client.post(
            "/tasks",
            data=json.dumps({"title": "User 2 Task"}),
            content_type="application/json",
            headers=headers2
        )

        # User 1 should only see their task
        response1 = client.get("/tasks", headers=headers1)
        data1 = json.loads(response1.data)
        assert len(data1["data"]) == 1
        assert data1["data"][0]["title"] == "User 1 Task"

        # User 2 should only see their task
        response2 = client.get("/tasks", headers=headers2)
        data2 = json.loads(response2.data)
        assert len(data2["data"]) == 1
        assert data2["data"][0]["title"] == "User 2 Task"


class TestTaskRetrieval:
    """Tests for GET /tasks/{id} endpoint."""

    def test_get_task_success(self, client, auth_headers):
        """Test retrieving an existing task."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Buy groceries"}),
            content_type="application/json",
            headers=auth_headers
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.get(f"/tasks/{task_id}", headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["id"] == task_id
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client, auth_headers):
        """Test retrieving a non-existent task returns 404."""
        response = client.get("/tasks/999", headers=auth_headers)

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["error"] == "task not found"

    def test_get_task_requires_token(self, client):
        """Test retrieving a task without token returns 401."""
        response = client.get("/tasks/1")

        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["error"] == "missing token"

    def test_get_task_not_owned_by_user(self, client):
        """Test that users cannot access tasks they don't own."""
        # Create first user and task
        token1 = create_user(client, "user1", "pass1")
        headers1 = {"Authorization": f"Bearer {token1}"}

        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "User 1 Task"}),
            content_type="application/json",
            headers=headers1
        )
        task_id = json.loads(create_response.data)["id"]

        # Create second user
        token2 = create_user(client, "user2", "pass2")
        headers2 = {"Authorization": f"Bearer {token2}"}

        # User 2 tries to access User 1's task
        response = client.get(f"/tasks/{task_id}", headers=headers2)

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["error"] == "task not found"


class TestTaskUpdate:
    """Tests for PUT /tasks/{id} endpoint."""

    def test_update_task_title(self, client, auth_headers):
        """Test updating only the title."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Old title"}),
            content_type="application/json",
            headers=auth_headers
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "New title"}),
            content_type="application/json",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["id"] == task_id
        assert data["title"] == "New title"
        assert data["status"] == "pending"

    def test_update_task_status(self, client, auth_headers):
        """Test updating only the status."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
            headers=auth_headers
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["id"] == task_id
        assert data["title"] == "Test task"
        assert data["status"] == "completed"

    def test_update_task_title_and_status(self, client, auth_headers):
        """Test updating both title and status."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Original"}),
            content_type="application/json",
            headers=auth_headers
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "Updated", "status": "in_progress"}),
            content_type="application/json",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["id"] == task_id
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_task_not_found(self, client, auth_headers):
        """Test updating a non-existent task returns 404."""
        response = client.put(
            "/tasks/999",
            data=json.dumps({"title": "Should fail"}),
            content_type="application/json",
            headers=auth_headers
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["error"] == "task not found"

    def test_update_task_empty_body(self, client, auth_headers):
        """Test updating a task with empty body (no changes)."""
        # Create a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Original"}),
            content_type="application/json",
            headers=auth_headers
        )
        task_id = json.loads(create_response.data)["id"]
        original_created_at = json.loads(create_response.data)["created_at"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({}),
            content_type="application/json",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["id"] == task_id
        assert data["title"] == "Original"
        assert data["created_at"] == original_created_at

    def test_update_task_requires_token(self, client):
        """Test updating a task without token returns 401."""
        response = client.put(
            "/tasks/1",
            data=json.dumps({"title": "New title"}),
            content_type="application/json"
        )

        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["error"] == "missing token"

    def test_update_task_not_owned_by_user(self, client):
        """Test that users cannot update tasks they don't own."""
        # Create first user and task
        token1 = create_user(client, "user1", "pass1")
        headers1 = {"Authorization": f"Bearer {token1}"}

        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "User 1 Task"}),
            content_type="application/json",
            headers=headers1
        )
        task_id = json.loads(create_response.data)["id"]

        # Create second user
        token2 = create_user(client, "user2", "pass2")
        headers2 = {"Authorization": f"Bearer {token2}"}

        # User 2 tries to update User 1's task
        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "Hacked!"}),
            content_type="application/json",
            headers=headers2
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["error"] == "task not found"

        # Verify the task wasn't actually updated
        verify_response = client.get(f"/tasks/{task_id}", headers=headers1)
        verify_data = json.loads(verify_response.data)
        assert verify_data["title"] == "User 1 Task"


class TestTaskInitialization:
    """Tests for database initialization."""

    def test_db_schema_exists(self, client, auth_headers):
        """Test that database schema is created on startup."""
        # Try to create and retrieve a task
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Schema test"}),
            content_type="application/json",
            headers=auth_headers
        )

        assert create_response.status_code == 201

        # Verify schema by checking we can query the table
        response = client.get("/tasks", headers=auth_headers)
        assert response.status_code == 200


class TestEmailNotifications:
    """Tests for async email notification system."""

    @patch('app.send_notification_email.delay')
    def test_notification_not_sent_without_email(self, mock_task, client):
        """Test that notification is not sent when task status changes to completed but user has no email."""
        token = create_user(client, "notifuser", "pass123")
        headers = {"Authorization": f"Bearer {token}"}

        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Complete this task"}),
            content_type="application/json",
            headers=headers
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
            headers=headers
        )

        assert response.status_code == 200
        mock_task.assert_not_called()

    @patch('app.send_notification_email.delay')
    def test_notification_sent_with_email(self, mock_task, client):
        """Test that notification task is triggered with user email."""
        client.post(
            "/auth/register",
            data=json.dumps({"username": "emailuser", "password": "pass123", "email": "user@example.com"}),
            content_type="application/json"
        )

        response = client.post(
            "/auth/login",
            data=json.dumps({"username": "emailuser", "password": "pass123"}),
            content_type="application/json"
        )
        token = json.loads(response.data)["token"]
        headers = {"Authorization": f"Bearer {token}"}

        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Important task"}),
            content_type="application/json",
            headers=headers
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
            headers=headers
        )

        assert response.status_code == 200
        mock_task.assert_called_once_with("user@example.com", "Important task")

    @patch('app.send_notification_email.delay')
    def test_notification_not_sent_if_no_email(self, mock_task, client):
        """Test that notification is not sent if user has no email."""
        token = create_user(client, "noemailuser", "pass123")
        headers = {"Authorization": f"Bearer {token}"}

        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Task without email"}),
            content_type="application/json",
            headers=headers
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
            headers=headers
        )

        assert response.status_code == 200
        mock_task.assert_not_called()

    @patch('app.send_notification_email.delay')
    def test_notification_not_sent_on_status_change_to_other(self, mock_task, client):
        """Test that notification is not sent when status changes to non-completed status."""
        client.post(
            "/auth/register",
            data=json.dumps({"username": "statususer", "password": "pass123", "email": "status@example.com"}),
            content_type="application/json"
        )

        response = client.post(
            "/auth/login",
            data=json.dumps({"username": "statususer", "password": "pass123"}),
            content_type="application/json"
        )
        token = json.loads(response.data)["token"]
        headers = {"Authorization": f"Bearer {token}"}

        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Work in progress"}),
            content_type="application/json",
            headers=headers
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "in_progress"}),
            content_type="application/json",
            headers=headers
        )

        assert response.status_code == 200
        mock_task.assert_not_called()

    @patch('app.send_notification_email.delay')
    def test_notification_not_sent_on_second_completion_update(self, mock_task, client):
        """Test that notification is only sent once, not on subsequent updates."""
        client.post(
            "/auth/register",
            data=json.dumps({"username": "onceonlyuser", "password": "pass123", "email": "once@example.com"}),
            content_type="application/json"
        )

        response = client.post(
            "/auth/login",
            data=json.dumps({"username": "onceonlyuser", "password": "pass123"}),
            content_type="application/json"
        )
        token = json.loads(response.data)["token"]
        headers = {"Authorization": f"Bearer {token}"}

        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Already done"}),
            content_type="application/json",
            headers=headers
        )
        task_id = json.loads(create_response.data)["id"]

        client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
            headers=headers
        )

        mock_task.reset_mock()

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "Already done - updated"}),
            content_type="application/json",
            headers=headers
        )

        assert response.status_code == 200
        mock_task.assert_not_called()


class TestPagination:
    """Tests for cursor-based pagination."""

    def test_list_tasks_pagination_empty(self, client, auth_headers):
        """Test pagination with no tasks."""
        response = client.get("/tasks", headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["data"] == []
        assert data["next_cursor"] is None
        assert data["total"] == 0

    def test_list_tasks_pagination_default_limit(self, client, auth_headers):
        """Test pagination with default limit of 20."""
        for i in range(5):
            client.post(
                "/tasks",
                data=json.dumps({"title": f"Task {i}"}),
                content_type="application/json",
                headers=auth_headers
            )

        response = client.get("/tasks", headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data["data"]) == 5
        assert data["next_cursor"] is None
        assert data["total"] == 5

    def test_list_tasks_pagination_custom_limit(self, client, auth_headers):
        """Test pagination with custom limit."""
        for i in range(10):
            client.post(
                "/tasks",
                data=json.dumps({"title": f"Task {i}"}),
                content_type="application/json",
                headers=auth_headers
            )

        response = client.get("/tasks?limit=3", headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data["data"]) == 3
        assert data["next_cursor"] is not None
        assert data["total"] == 10

    def test_list_tasks_pagination_cursor(self, client, auth_headers):
        """Test pagination with cursor."""
        task_ids = []
        for i in range(5):
            create_response = client.post(
                "/tasks",
                data=json.dumps({"title": f"Task {i}"}),
                content_type="application/json",
                headers=auth_headers
            )
            task_ids.append(json.loads(create_response.data)["id"])

        response1 = client.get("/tasks?limit=2", headers=auth_headers)
        data1 = json.loads(response1.data)
        assert len(data1["data"]) == 2
        assert data1["next_cursor"] is not None

        cursor = data1["next_cursor"]
        response2 = client.get(f"/tasks?cursor={cursor}&limit=2", headers=auth_headers)
        data2 = json.loads(response2.data)
        assert len(data2["data"]) == 2
        assert data2["next_cursor"] is not None

        cursor2 = data2["next_cursor"]
        response3 = client.get(f"/tasks?cursor={cursor2}&limit=2", headers=auth_headers)
        data3 = json.loads(response3.data)
        assert len(data3["data"]) == 1
        assert data3["next_cursor"] is None

    def test_list_tasks_pagination_limit_bounds(self, client, auth_headers):
        """Test that limit is clamped to valid range."""
        for i in range(5):
            client.post(
                "/tasks",
                data=json.dumps({"title": f"Task {i}"}),
                content_type="application/json",
                headers=auth_headers
            )

        response_high = client.get("/tasks?limit=200", headers=auth_headers)
        data_high = json.loads(response_high.data)
        assert len(data_high["data"]) == 5

        response_low = client.get("/tasks?limit=0", headers=auth_headers)
        data_low = json.loads(response_low.data)
        assert len(data_low["data"]) == 5

        response_negative = client.get("/tasks?limit=-5", headers=auth_headers)
        data_negative = json.loads(response_negative.data)
        assert len(data_negative["data"]) == 5

    def test_list_tasks_pagination_multiple_users(self, client):
        """Test that pagination only returns user's own tasks."""
        token1 = create_user(client, "user1", "pass1")
        headers1 = {"Authorization": f"Bearer {token1}"}

        token2 = create_user(client, "user2", "pass2")
        headers2 = {"Authorization": f"Bearer {token2}"}

        for i in range(5):
            client.post(
                "/tasks",
                data=json.dumps({"title": f"User1 Task {i}"}),
                content_type="application/json",
                headers=headers1
            )

        for i in range(3):
            client.post(
                "/tasks",
                data=json.dumps({"title": f"User2 Task {i}"}),
                content_type="application/json",
                headers=headers2
            )

        response1 = client.get("/tasks", headers=headers1)
        data1 = json.loads(response1.data)
        assert data1["total"] == 5
        assert len(data1["data"]) == 5

        response2 = client.get("/tasks", headers=headers2)
        data2 = json.loads(response2.data)
        assert data2["total"] == 3
        assert len(data2["data"]) == 3


class TestRateLimiting:
    """Tests for rate limiting."""

    def test_rate_limit_decorator_applied(self, client, auth_headers):
        """Test that rate limit decorators are applied to endpoints."""
        from app import app as flask_app

        response = client.get("/tasks", headers=auth_headers)
        assert response.status_code == 200

        response = client.post(
            "/auth/register",
            data=json.dumps({"username": "testuser1", "password": "pass"}),
            content_type="application/json"
        )
        assert response.status_code in [201, 409]

        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test"}),
            content_type="application/json",
            headers=auth_headers
        )
        assert create_response.status_code == 201

    def test_rate_limit_key_function(self, client, auth_headers):
        """Test that rate limit key function uses user ID."""
        from app import get_rate_limit_key
        from flask import request

        with client:
            client.get("/tasks", headers=auth_headers)

            with app.test_request_context(
                "/tasks",
                headers=auth_headers
            ):
                key = get_rate_limit_key()
                assert key.startswith("user:")

    def test_rate_limit_unauthenticated_uses_ip(self, client):
        """Test that unauthenticated requests use IP for rate limiting."""
        from app import get_rate_limit_key

        with app.test_request_context("/auth/login"):
            key = get_rate_limit_key()
            assert not key.startswith("user:")

    def test_rate_limit_returns_429(self):
        """Test that rate limit returns 429 status code when exceeded."""
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
        os.environ["DATABASE"] = TEST_DB
        init_db()

        try:
            app.config['RATELIMIT_ENABLED'] = True
            limiter.enabled = True

            client = app.test_client()

            client.post(
                "/auth/register",
                data=json.dumps({"username": "limituser", "password": "pass"}),
                content_type="application/json"
            )

            count_429 = 0
            for i in range(200):
                response = client.post(
                    "/auth/login",
                    data=json.dumps({"username": "limituser", "password": "pass"}),
                    content_type="application/json"
                )
                if response.status_code == 429:
                    count_429 += 1

            assert count_429 > 0
        finally:
            if os.path.exists(TEST_DB):
                os.remove(TEST_DB)
            app.config['RATELIMIT_ENABLED'] = False
            limiter.enabled = False
