"""
Tests for the Task Management API
"""

import pytest
import json
import os
import sqlite3
from unittest.mock import patch, MagicMock
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


@pytest.fixture
def mock_celery_task(monkeypatch):
    """Mock the Celery send_notification_email task."""
    mock_task = MagicMock()
    mock_task.delay = MagicMock(return_value=None)
    monkeypatch.setattr(app_module, "send_notification_email", mock_task)
    return mock_task


def register_user(client, username, password, email=None):
    """Helper to register a user and return the token."""
    payload = {"username": username, "password": password}
    if email:
        payload["email"] = email
    response = client.post(
        "/auth/register",
        data=json.dumps(payload),
        content_type="application/json"
    )
    data = json.loads(response.data)
    return data.get("token"), data.get("user_id")


def login_user(client, username, password):
    """Helper to login a user and return the token."""
    response = client.post(
        "/auth/login",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json"
    )
    data = json.loads(response.data)
    return data.get("token"), data.get("user_id")


class TestRegister:
    """Tests for POST /auth/register"""

    def test_register_success(self, client):
        """Register a new user successfully."""
        response = client.post(
            "/auth/register",
            data=json.dumps({"username": "alice", "password": "secret123"}),
            content_type="application/json"
        )
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["username"] == "alice"
        assert data["token"] is not None
        assert data["user_id"] is not None

    def test_register_missing_username(self, client):
        """Return 400 when username is missing."""
        response = client.post(
            "/auth/register",
            data=json.dumps({"username": "", "password": "secret123"}),
            content_type="application/json"
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] == "username is required"

    def test_register_missing_password(self, client):
        """Return 400 when password is missing."""
        response = client.post(
            "/auth/register",
            data=json.dumps({"username": "alice", "password": ""}),
            content_type="application/json"
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] == "password is required"

    def test_register_duplicate_username(self, client):
        """Return 409 when username already exists."""
        register_user(client, "alice", "secret123")
        response = client.post(
            "/auth/register",
            data=json.dumps({"username": "alice", "password": "different"}),
            content_type="application/json"
        )
        assert response.status_code == 409
        data = json.loads(response.data)
        assert data["error"] == "username already exists"

    def test_register_whitespace_username(self, client):
        """Return 400 when username is whitespace only."""
        response = client.post(
            "/auth/register",
            data=json.dumps({"username": "   ", "password": "secret123"}),
            content_type="application/json"
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] == "username is required"


class TestLogin:
    """Tests for POST /auth/login"""

    def test_login_success(self, client):
        """Login with valid credentials."""
        register_user(client, "alice", "secret123")
        response = client.post(
            "/auth/login",
            data=json.dumps({"username": "alice", "password": "secret123"}),
            content_type="application/json"
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["username"] == "alice"
        assert data["token"] is not None
        assert data["user_id"] is not None

    def test_login_invalid_username(self, client):
        """Return 401 with invalid username."""
        response = client.post(
            "/auth/login",
            data=json.dumps({"username": "nonexistent", "password": "secret123"}),
            content_type="application/json"
        )
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["error"] == "invalid username or password"

    def test_login_invalid_password(self, client):
        """Return 401 with invalid password."""
        register_user(client, "alice", "secret123")
        response = client.post(
            "/auth/login",
            data=json.dumps({"username": "alice", "password": "wrongpassword"}),
            content_type="application/json"
        )
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["error"] == "invalid username or password"

    def test_login_missing_username(self, client):
        """Return 400 when username is missing."""
        response = client.post(
            "/auth/login",
            data=json.dumps({"username": "", "password": "secret123"}),
            content_type="application/json"
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] == "username and password are required"

    def test_login_missing_password(self, client):
        """Return 400 when password is missing."""
        response = client.post(
            "/auth/login",
            data=json.dumps({"username": "alice", "password": ""}),
            content_type="application/json"
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] == "username and password are required"


class TestCreateTask:
    """Tests for POST /tasks"""

    def test_create_task_success(self, client):
        """Create a task with valid title and auth."""
        token, user_id = register_user(client, "alice", "secret123")
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "Buy groceries"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert data["id"] is not None
        assert data["created_at"] is not None
        assert data["owner_id"] == user_id

    def test_create_task_missing_auth(self, client):
        """Return 401 when authorization header is missing."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "Buy groceries"}),
            content_type="application/json"
        )
        assert response.status_code == 401
        data = json.loads(response.data)
        assert "authorization header" in data["error"].lower()

    def test_create_task_invalid_token(self, client):
        """Return 401 when token is invalid."""
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "Buy groceries"}),
            content_type="application/json",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401
        data = json.loads(response.data)
        assert "invalid or expired token" in data["error"].lower()

    def test_create_task_missing_title(self, client):
        """Return 400 when title is missing."""
        token, _ = register_user(client, "alice", "secret123")
        response = client.post(
            "/tasks",
            data=json.dumps({"title": ""}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] == "title is required"

    def test_create_task_no_json(self, client):
        """Return 400 when no JSON body."""
        token, _ = register_user(client, "alice", "secret123")
        response = client.post(
            "/tasks",
            data=json.dumps({}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] == "title is required"

    def test_create_task_whitespace_only(self, client):
        """Return 400 when title is whitespace only."""
        token, _ = register_user(client, "alice", "secret123")
        response = client.post(
            "/tasks",
            data=json.dumps({"title": "   "}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] == "title is required"


class TestListTasks:
    """Tests for GET /tasks"""

    def test_list_tasks_empty(self, client):
        """List tasks returns empty array when no tasks."""
        token, _ = register_user(client, "alice", "secret123")
        response = client.get(
            "/tasks",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == []

    def test_list_tasks_single(self, client):
        """List tasks returns single task."""
        token, _ = register_user(client, "alice", "secret123")
        client.post(
            "/tasks",
            data=json.dumps({"title": "Task 1"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        response = client.get(
            "/tasks",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 1
        assert data[0]["title"] == "Task 1"

    def test_list_tasks_multiple_ordered(self, client):
        """List tasks returns multiple tasks ordered by created_at descending."""
        import time
        token, _ = register_user(client, "alice", "secret123")
        client.post(
            "/tasks",
            data=json.dumps({"title": "Task 1"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        time.sleep(0.01)
        client.post(
            "/tasks",
            data=json.dumps({"title": "Task 2"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        time.sleep(0.01)
        client.post(
            "/tasks",
            data=json.dumps({"title": "Task 3"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )

        response = client.get(
            "/tasks",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 3
        assert data[0]["title"] == "Task 3"
        assert data[1]["title"] == "Task 2"
        assert data[2]["title"] == "Task 1"

    def test_list_tasks_missing_auth(self, client):
        """Return 401 when authorization header is missing."""
        response = client.get("/tasks")
        assert response.status_code == 401
        data = json.loads(response.data)
        assert "authorization header" in data["error"].lower()

    def test_list_tasks_isolation(self, client):
        """Users only see their own tasks."""
        token1, _ = register_user(client, "alice", "secret123")
        token2, _ = register_user(client, "bob", "secret456")

        client.post(
            "/tasks",
            data=json.dumps({"title": "Alice's task"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token1}"}
        )
        client.post(
            "/tasks",
            data=json.dumps({"title": "Bob's task"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token2}"}
        )

        response = client.get(
            "/tasks",
            headers={"Authorization": f"Bearer {token1}"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 1
        assert data[0]["title"] == "Alice's task"


class TestGetTask:
    """Tests for GET /tasks/{id}"""

    def test_get_task_success(self, client):
        """Get a task by ID."""
        token, user_id = register_user(client, "alice", "secret123")
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.get(
            f"/tasks/{task_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["id"] == task_id
        assert data["title"] == "Test task"
        assert data["status"] == "pending"
        assert data["owner_id"] == user_id

    def test_get_task_not_found(self, client):
        """Return 404 when task not found."""
        token, _ = register_user(client, "alice", "secret123")
        response = client.get(
            "/tasks/999",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["error"] == "task not found"

    def test_get_task_missing_auth(self, client):
        """Return 401 when authorization header is missing."""
        response = client.get("/tasks/1")
        assert response.status_code == 401
        data = json.loads(response.data)
        assert "authorization header" in data["error"].lower()

    def test_get_task_other_user(self, client):
        """Return 404 when accessing another user's task."""
        token1, _ = register_user(client, "alice", "secret123")
        token2, _ = register_user(client, "bob", "secret456")

        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Alice's task"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token1}"}
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.get(
            f"/tasks/{task_id}",
            headers={"Authorization": f"Bearer {token2}"}
        )
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["error"] == "task not found"


class TestUpdateTask:
    """Tests for PUT /tasks/{id}"""

    def test_update_task_title(self, client):
        """Update task title."""
        token, _ = register_user(client, "alice", "secret123")
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Old title"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "New title"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["title"] == "New title"
        assert data["status"] == "pending"

    def test_update_task_status(self, client):
        """Update task status."""
        token, _ = register_user(client, "alice", "secret123")
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Test task"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "completed"
        assert data["title"] == "Test task"

    def test_update_task_title_and_status(self, client):
        """Update both title and status."""
        token, _ = register_user(client, "alice", "secret123")
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Original"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "Updated", "status": "in_progress"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_task_not_found(self, client):
        """Return 404 when updating non-existent task."""
        token, _ = register_user(client, "alice", "secret123")
        response = client.put(
            "/tasks/999",
            data=json.dumps({"title": "New title"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["error"] == "task not found"

    def test_update_task_empty_title(self, client):
        """Empty title is treated as removing the value - should use current."""
        token, _ = register_user(client, "alice", "secret123")
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Original"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": ""}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["title"] == "Original"

    def test_update_task_missing_auth(self, client):
        """Return 401 when authorization header is missing."""
        response = client.put(
            "/tasks/1",
            data=json.dumps({"title": "New title"}),
            content_type="application/json"
        )
        assert response.status_code == 401
        data = json.loads(response.data)
        assert "authorization header" in data["error"].lower()

    def test_update_task_other_user(self, client):
        """Return 404 when updating another user's task."""
        token1, _ = register_user(client, "alice", "secret123")
        token2, _ = register_user(client, "bob", "secret456")

        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Alice's task"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token1}"}
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "Hacked!"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token2}"}
        )
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["error"] == "task not found"


class TestHealthEndpoint:
    """Tests for GET /health"""

    def test_health_check(self, client):
        """Health endpoint returns ok."""
        response = client.get("/health")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "ok"


class TestNotificationTrigger:
    """Tests for email notification trigger on task completion"""

    def test_notification_triggered_on_completion(self, client, mock_celery_task):
        """Email notification is triggered when task status changes to completed."""
        token, _ = register_user(client, "alice", "secret123", "alice@example.com")
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Important task"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        mock_celery_task.delay.assert_called_once_with("alice@example.com", "Important task")

    def test_notification_not_triggered_on_other_status(self, client, mock_celery_task):
        """Email notification is NOT triggered when status changes to non-completed."""
        token, _ = register_user(client, "alice", "secret123", "alice@example.com")
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Task"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "in_progress"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        mock_celery_task.delay.assert_not_called()

    def test_notification_not_triggered_if_already_completed(self, client, mock_celery_task):
        """Email notification is NOT triggered if task is already completed."""
        token, _ = register_user(client, "alice", "secret123", "alice@example.com")
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Task"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        task_id = json.loads(create_response.data)["id"]

        # First set to completed
        client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        mock_celery_task.delay.reset_mock()

        # Try to update again while already completed
        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        mock_celery_task.delay.assert_not_called()

    def test_notification_contains_correct_task_title(self, client, mock_celery_task):
        """Notification is sent with correct task title."""
        token, _ = register_user(client, "alice", "secret123", "alice@example.com")
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Buy birthday gift for mom"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        task_id = json.loads(create_response.data)["id"]

        client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        mock_celery_task.delay.assert_called_once()
        call_args = mock_celery_task.delay.call_args
        assert call_args[0][1] == "Buy birthday gift for mom"

    def test_notification_not_triggered_without_email(self, client, mock_celery_task):
        """Email notification is NOT triggered if user has no email set."""
        token, _ = register_user(client, "alice", "secret123")
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Task"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        task_id = json.loads(create_response.data)["id"]

        response = client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        mock_celery_task.delay.assert_not_called()

    def test_notification_title_updated_when_completing(self, client, mock_celery_task):
        """Notification is sent with the title at time of completion."""
        token, _ = register_user(client, "alice", "secret123", "alice@example.com")
        create_response = client.post(
            "/tasks",
            data=json.dumps({"title": "Original title"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        task_id = json.loads(create_response.data)["id"]

        client.put(
            f"/tasks/{task_id}",
            data=json.dumps({"title": "Updated title", "status": "completed"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"}
        )
        mock_celery_task.delay.assert_called_once_with("alice@example.com", "Updated title")
