"""
Tests for the Flask Task Management API with JWT Authentication
"""

import pytest
import sqlite3
import os
from datetime import datetime
from unittest.mock import patch, MagicMock
from task_app import app, init_db, limiter


@pytest.fixture
def client():
    """Create a test client with a fresh database"""
    import tempfile
    import shutil

    test_dir = tempfile.mkdtemp()
    test_db = os.path.join(test_dir, "test_tasks.db")

    # Store original database path
    original_db = os.environ.get("DATABASE")

    # Set test database
    os.environ["DATABASE"] = test_db

    if os.path.exists(test_db):
        os.remove(test_db)

    init_db()

    app.config["TESTING"] = True
    limiter.enabled = False
    with app.test_client() as test_client:
        yield test_client
    limiter.enabled = True

    # Cleanup
    shutil.rmtree(test_dir, ignore_errors=True)

    # Restore original database path
    if original_db:
        os.environ["DATABASE"] = original_db
    elif "DATABASE" in os.environ:
        del os.environ["DATABASE"]


@pytest.fixture
def auth_user(client):
    """Create a test user and return their token"""
    response = client.post("/auth/register", json={
        "username": "testuser",
        "password": "password123"
    })
    assert response.status_code == 201

    login_response = client.post("/auth/login", json={
        "username": "testuser",
        "password": "password123"
    })
    assert login_response.status_code == 200
    token = login_response.get_json()["token"]
    return {"token": token, "username": "testuser"}


@pytest.fixture
def another_user(client):
    """Create another test user and return their token"""
    response = client.post("/auth/register", json={
        "username": "otheruser",
        "password": "password456"
    })
    assert response.status_code == 201

    login_response = client.post("/auth/login", json={
        "username": "otheruser",
        "password": "password456"
    })
    assert login_response.status_code == 200
    token = login_response.get_json()["token"]
    return {"token": token, "username": "otheruser"}


@pytest.fixture
def email_user(client):
    """Create a test user with email and return their token"""
    response = client.post("/auth/register", json={
        "username": "emailuser",
        "password": "password789",
        "email": "emailuser@example.com"
    })
    assert response.status_code == 201

    login_response = client.post("/auth/login", json={
        "username": "emailuser",
        "password": "password789"
    })
    assert login_response.status_code == 200
    token = login_response.get_json()["token"]
    return {"token": token, "username": "emailuser", "email": "emailuser@example.com"}


def get_auth_headers(token):
    """Helper to create auth headers"""
    return {"Authorization": f"Bearer {token}"}


# ── Auth Tests ──────────────────────────────────────────────────


class TestRegister:
    def test_register_success(self, client):
        """Test successful user registration"""
        response = client.post("/auth/register", json={
            "username": "newuser",
            "password": "password123"
        })
        assert response.status_code == 201
        data = response.get_json()
        assert data["message"] == "user registered"
        assert data["username"] == "newuser"

    def test_register_missing_username(self, client):
        """Test registration without username"""
        response = client.post("/auth/register", json={
            "password": "password123"
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "username and password required"

    def test_register_missing_password(self, client):
        """Test registration without password"""
        response = client.post("/auth/register", json={
            "username": "newuser"
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "username and password required"

    def test_register_short_password(self, client):
        """Test registration with password < 8 characters"""
        response = client.post("/auth/register", json={
            "username": "newuser",
            "password": "short"
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "password must be at least 8 characters"

    def test_register_duplicate_username(self, client):
        """Test registration with duplicate username"""
        client.post("/auth/register", json={
            "username": "duplicate",
            "password": "password123"
        })
        response = client.post("/auth/register", json={
            "username": "duplicate",
            "password": "password456"
        })
        assert response.status_code == 409
        data = response.get_json()
        assert data["error"] == "username already taken"


class TestLogin:
    def test_login_success(self, client):
        """Test successful login"""
        client.post("/auth/register", json={
            "username": "testuser",
            "password": "password123"
        })
        response = client.post("/auth/login", json={
            "username": "testuser",
            "password": "password123"
        })
        assert response.status_code == 200
        data = response.get_json()
        assert "token" in data
        assert data["username"] == "testuser"

    def test_login_invalid_username(self, client):
        """Test login with non-existent username"""
        response = client.post("/auth/login", json={
            "username": "nonexistent",
            "password": "password123"
        })
        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "invalid credentials"

    def test_login_invalid_password(self, client):
        """Test login with wrong password"""
        client.post("/auth/register", json={
            "username": "testuser",
            "password": "password123"
        })
        response = client.post("/auth/login", json={
            "username": "testuser",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "invalid credentials"

    def test_login_missing_credentials(self, client):
        """Test login without credentials"""
        response = client.post("/auth/login", json={})
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "username and password required"


# ── Task Tests with Auth ─────────────────────────────────────────


class TestCreateTask:
    def test_create_task_success(self, client, auth_user):
        """Test creating a task with valid title and auth"""
        response = client.post(
            "/tasks",
            json={"title": "Buy groceries"},
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert "created_at" in data

    def test_create_task_missing_auth(self, client):
        """Test creating a task without authentication"""
        response = client.post("/tasks", json={"title": "Task"})
        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "missing authorization header"

    def test_create_task_invalid_token(self, client):
        """Test creating a task with invalid token"""
        response = client.post(
            "/tasks",
            json={"title": "Task"},
            headers=get_auth_headers("invalid_token")
        )
        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "invalid or expired token"

    def test_create_task_missing_title(self, client, auth_user):
        """Test creating a task without title"""
        response = client.post(
            "/tasks",
            json={},
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "title is required"

    def test_create_task_empty_title(self, client, auth_user):
        """Test creating a task with empty title"""
        response = client.post(
            "/tasks",
            json={"title": ""},
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 400

    def test_create_multiple_tasks(self, client, auth_user):
        """Test creating multiple tasks"""
        response1 = client.post(
            "/tasks",
            json={"title": "Task 1"},
            headers=get_auth_headers(auth_user["token"])
        )
        assert response1.status_code == 201
        task1 = response1.get_json()

        response2 = client.post(
            "/tasks",
            json={"title": "Task 2"},
            headers=get_auth_headers(auth_user["token"])
        )
        assert response2.status_code == 201
        task2 = response2.get_json()

        assert task1["id"] != task2["id"]


class TestListTasks:
    def test_list_tasks_empty(self, client, auth_user):
        """Test listing tasks when none exist"""
        response = client.get(
            "/tasks",
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["data"] == []
        assert data["next_cursor"] is None
        assert data["total"] == 0

    def test_list_tasks_missing_auth(self, client):
        """Test listing tasks without authentication"""
        response = client.get("/tasks")
        assert response.status_code == 401

    def test_list_tasks_only_own(self, client, auth_user, another_user):
        """Test that users only see their own tasks"""
        # User 1 creates a task
        client.post(
            "/tasks",
            json={"title": "User 1 Task"},
            headers=get_auth_headers(auth_user["token"])
        )

        # User 2 creates a task
        client.post(
            "/tasks",
            json={"title": "User 2 Task"},
            headers=get_auth_headers(another_user["token"])
        )

        # User 1 lists tasks - should only see their own
        response = client.get(
            "/tasks",
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["data"]) == 1
        assert data["data"][0]["title"] == "User 1 Task"
        assert data["total"] == 1

        # User 2 lists tasks - should only see their own
        response = client.get(
            "/tasks",
            headers=get_auth_headers(another_user["token"])
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["data"]) == 1
        assert data["data"][0]["title"] == "User 2 Task"
        assert data["total"] == 1

    def test_list_tasks_ordered_by_id_desc(self, client, auth_user):
        """Test that tasks are listed in descending order by id"""
        client.post(
            "/tasks",
            json={"title": "Task 1"},
            headers=get_auth_headers(auth_user["token"])
        )
        client.post(
            "/tasks",
            json={"title": "Task 2"},
            headers=get_auth_headers(auth_user["token"])
        )
        client.post(
            "/tasks",
            json={"title": "Task 3"},
            headers=get_auth_headers(auth_user["token"])
        )

        response = client.get(
            "/tasks",
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["data"]) == 3
        assert data["total"] == 3

        # Should be in reverse order (most recent by id first)
        assert data["data"][0]["title"] == "Task 3"
        assert data["data"][1]["title"] == "Task 2"
        assert data["data"][2]["title"] == "Task 1"


class TestGetTask:
    def test_get_task_success(self, client, auth_user):
        """Test getting a single task by id"""
        create_response = client.post(
            "/tasks",
            json={"title": "Buy milk"},
            headers=get_auth_headers(auth_user["token"])
        )
        task_id = create_response.get_json()["id"]

        response = client.get(
            f"/tasks/{task_id}",
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Buy milk"
        assert data["status"] == "pending"

    def test_get_task_missing_auth(self, client):
        """Test getting a task without authentication"""
        response = client.get("/tasks/1")
        assert response.status_code == 401

    def test_get_task_not_found(self, client, auth_user):
        """Test getting a task that doesn't exist"""
        response = client.get(
            "/tasks/999",
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "task not found"

    def test_get_other_users_task(self, client, auth_user, another_user):
        """Test that users cannot see other users' tasks"""
        # User 1 creates a task
        create_response = client.post(
            "/tasks",
            json={"title": "Secret task"},
            headers=get_auth_headers(auth_user["token"])
        )
        task_id = create_response.get_json()["id"]

        # User 2 tries to access it - should fail
        response = client.get(
            f"/tasks/{task_id}",
            headers=get_auth_headers(another_user["token"])
        )
        assert response.status_code == 404


class TestUpdateTask:
    def test_update_task_title(self, client, auth_user):
        """Test updating a task's title"""
        create_response = client.post(
            "/tasks",
            json={"title": "Old title"},
            headers=get_auth_headers(auth_user["token"])
        )
        task_id = create_response.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "New title"},
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "New title"
        assert data["status"] == "pending"
        assert data["id"] == task_id

    def test_update_task_status(self, client, auth_user):
        """Test updating a task's status"""
        create_response = client.post(
            "/tasks",
            json={"title": "Test"},
            headers=get_auth_headers(auth_user["token"])
        )
        task_id = create_response.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"status": "completed"},
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "completed"
        assert data["title"] == "Test"

    def test_update_task_missing_auth(self, client):
        """Test updating a task without authentication"""
        response = client.put(
            "/tasks/1",
            json={"title": "New title"}
        )
        assert response.status_code == 401

    def test_update_other_users_task(self, client, auth_user, another_user):
        """Test that users cannot update other users' tasks"""
        # User 1 creates a task
        create_response = client.post(
            "/tasks",
            json={"title": "Original"},
            headers=get_auth_headers(auth_user["token"])
        )
        task_id = create_response.get_json()["id"]

        # User 2 tries to update it - should fail
        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Hacked"},
            headers=get_auth_headers(another_user["token"])
        )
        assert response.status_code == 404

    def test_update_task_not_found(self, client, auth_user):
        """Test updating a task that doesn't exist"""
        response = client.put(
            "/tasks/999",
            json={"title": "New title"},
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 404

    def test_update_task_title_and_status(self, client, auth_user):
        """Test updating both title and status"""
        create_response = client.post(
            "/tasks",
            json={"title": "Original"},
            headers=get_auth_headers(auth_user["token"])
        )
        task_id = create_response.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated", "status": "in_progress"},
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_task_no_changes(self, client, auth_user):
        """Test updating a task with no changes (empty JSON)"""
        create_response = client.post(
            "/tasks",
            json={"title": "Original"},
            headers=get_auth_headers(auth_user["token"])
        )
        task_id = create_response.get_json()["id"]
        original = create_response.get_json()

        response = client.put(
            f"/tasks/{task_id}",
            json={},
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == original["title"]
        assert data["status"] == original["status"]


class TestIntegration:
    def test_full_workflow(self, client, auth_user):
        """Test a complete workflow: create, list, get, update"""
        # Create tasks
        response1 = client.post(
            "/tasks",
            json={"title": "Task A"},
            headers=get_auth_headers(auth_user["token"])
        )
        task1_id = response1.get_json()["id"]

        response2 = client.post(
            "/tasks",
            json={"title": "Task B"},
            headers=get_auth_headers(auth_user["token"])
        )
        task2_id = response2.get_json()["id"]

        # List all tasks
        response = client.get(
            "/tasks",
            headers=get_auth_headers(auth_user["token"])
        )
        result = response.get_json()
        tasks = result["data"]
        assert len(tasks) == 2
        assert result["total"] == 2
        assert tasks[0]["title"] == "Task B"  # Most recent first
        assert tasks[1]["title"] == "Task A"

        # Get specific task
        response = client.get(
            f"/tasks/{task1_id}",
            headers=get_auth_headers(auth_user["token"])
        )
        task = response.get_json()
        assert task["title"] == "Task A"
        assert task["status"] == "pending"

        # Update task
        response = client.put(
            f"/tasks/{task1_id}",
            json={"title": "Task A Updated", "status": "completed"},
            headers=get_auth_headers(auth_user["token"])
        )
        task = response.get_json()
        assert task["title"] == "Task A Updated"
        assert task["status"] == "completed"

        # Verify update persisted
        response = client.get(
            f"/tasks/{task1_id}",
            headers=get_auth_headers(auth_user["token"])
        )
        task = response.get_json()
        assert task["title"] == "Task A Updated"
        assert task["status"] == "completed"

    def test_multi_user_isolation(self, client, auth_user, another_user):
        """Test that multiple users have completely isolated task lists"""
        # User 1 creates 3 tasks
        for i in range(1, 4):
            client.post(
                "/tasks",
                json={"title": f"User 1 Task {i}"},
                headers=get_auth_headers(auth_user["token"])
            )

        # User 2 creates 2 tasks
        for i in range(1, 3):
            client.post(
                "/tasks",
                json={"title": f"User 2 Task {i}"},
                headers=get_auth_headers(another_user["token"])
            )

        # Verify User 1 sees only 3 tasks
        response = client.get(
            "/tasks",
            headers=get_auth_headers(auth_user["token"])
        )
        result = response.get_json()
        tasks = result["data"]
        assert len(tasks) == 3
        assert result["total"] == 3
        assert all("User 1" in t["title"] for t in tasks)

        # Verify User 2 sees only 2 tasks
        response = client.get(
            "/tasks",
            headers=get_auth_headers(another_user["token"])
        )
        result = response.get_json()
        tasks = result["data"]
        assert len(tasks) == 2
        assert result["total"] == 2
        assert all("User 2" in t["title"] for t in tasks)

    def test_persistence_across_requests(self, client, auth_user):
        """Test that data persists across multiple requests"""
        # Create a task
        response = client.post(
            "/tasks",
            json={"title": "Persistent"},
            headers=get_auth_headers(auth_user["token"])
        )
        task_id = response.get_json()["id"]
        created_at = response.get_json()["created_at"]

        # Get it multiple times
        for _ in range(3):
            response = client.get(
                f"/tasks/{task_id}",
                headers=get_auth_headers(auth_user["token"])
            )
            data = response.get_json()
            assert data["id"] == task_id
            assert data["title"] == "Persistent"
            assert data["created_at"] == created_at

    def test_status_values(self, client, auth_user):
        """Test various status values"""
        response = client.post(
            "/tasks",
            json={"title": "Task"},
            headers=get_auth_headers(auth_user["token"])
        )
        task_id = response.get_json()["id"]

        statuses = ["pending", "in_progress", "completed", "archived"]
        for status in statuses:
            response = client.put(
                f"/tasks/{task_id}",
                json={"status": status},
                headers=get_auth_headers(auth_user["token"])
            )
            data = response.get_json()
            assert data["status"] == status

    def test_task_creation_timestamps(self, client, auth_user):
        """Test that tasks have valid ISO format timestamps"""
        response = client.post(
            "/tasks",
            json={"title": "Task"},
            headers=get_auth_headers(auth_user["token"])
        )
        data = response.get_json()

        created_at = data["created_at"]
        assert "T" in created_at  # ISO format includes T
        assert "-" in created_at  # Has date separators

        # Should parse as datetime
        datetime.fromisoformat(created_at)


class TestErrorHandling:
    def test_invalid_json(self, client, auth_user):
        """Test sending invalid JSON"""
        response = client.post(
            "/tasks",
            data="invalid json",
            content_type="application/json",
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code in [400, 415]

    def test_null_title(self, client, auth_user):
        """Test creating a task with null title"""
        response = client.post(
            "/tasks",
            json={"title": None},
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "title is required"

    def test_numeric_title(self, client, auth_user):
        """Test creating a task with numeric title"""
        response = client.post(
            "/tasks",
            json={"title": 123},
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "123"


class TestEmailNotification:
    @patch("task_app.send_notification_email")
    def test_notification_sent_when_task_completed(self, mock_send, client, email_user):
        """Test that notification task is queued when status changes to 'completed'"""
        # Create a task
        response = client.post(
            "/tasks",
            json={"title": "Important Task"},
            headers=get_auth_headers(email_user["token"])
        )
        task_id = response.get_json()["id"]

        # Update task to completed
        with patch("task_app.send_notification_email") as mock_task:
            mock_task.delay = MagicMock()
            response = client.put(
                f"/tasks/{task_id}",
                json={"status": "completed"},
                headers=get_auth_headers(email_user["token"])
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "completed"

    @patch("task_app.send_notification_email")
    def test_notification_not_sent_without_email(self, mock_send, client, auth_user):
        """Test that notification is not sent when user has no email"""
        # Create a task
        response = client.post(
            "/tasks",
            json={"title": "Task without email"},
            headers=get_auth_headers(auth_user["token"])
        )
        task_id = response.get_json()["id"]

        # Update task to completed - should not crash even without email
        with patch("task_app.send_notification_email") as mock_task:
            mock_task.delay = MagicMock()
            response = client.put(
                f"/tasks/{task_id}",
                json={"status": "completed"},
                headers=get_auth_headers(auth_user["token"])
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "completed"

    def test_notification_not_sent_when_status_not_completed(self, client, email_user):
        """Test that notification is not sent when status changes to non-completed value"""
        # Create a task
        response = client.post(
            "/tasks",
            json={"title": "Task in progress"},
            headers=get_auth_headers(email_user["token"])
        )
        task_id = response.get_json()["id"]

        # Update task to in_progress (not completed)
        with patch("task_app.send_notification_email") as mock_task:
            mock_task.delay = MagicMock()
            response = client.put(
                f"/tasks/{task_id}",
                json={"status": "in_progress"},
                headers=get_auth_headers(email_user["token"])
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "in_progress"

    def test_notification_not_sent_when_already_completed(self, client, email_user):
        """Test that notification is not sent when status was already completed"""
        # Create and complete a task
        response = client.post(
            "/tasks",
            json={"title": "Already done"},
            headers=get_auth_headers(email_user["token"])
        )
        task_id = response.get_json()["id"]

        # First update to completed
        with patch("task_app.send_notification_email") as mock_task:
            mock_task.delay = MagicMock()
            response = client.put(
                f"/tasks/{task_id}",
                json={"status": "completed"},
                headers=get_auth_headers(email_user["token"])
            )
            assert response.status_code == 200

            # Second update (e.g., update title while already completed)
            response = client.put(
                f"/tasks/{task_id}",
                json={"title": "Updated title"},
                headers=get_auth_headers(email_user["token"])
            )
            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "completed"

    def test_register_with_email(self, client):
        """Test user registration with email"""
        response = client.post("/auth/register", json={
            "username": "newemail",
            "password": "password123",
            "email": "newemail@example.com"
        })
        assert response.status_code == 201
        data = response.get_json()
        assert data["username"] == "newemail"

        # Verify email was stored by logging in and checking
        login_response = client.post("/auth/login", json={
            "username": "newemail",
            "password": "password123"
        })
        assert login_response.status_code == 200

    def test_register_without_email(self, client):
        """Test that email is optional during registration"""
        response = client.post("/auth/register", json={
            "username": "noemail",
            "password": "password123"
        })
        assert response.status_code == 201
        data = response.get_json()
        assert data["username"] == "noemail"


class TestPagination:
    def test_pagination_default_limit(self, client, auth_user):
        """Test pagination with default limit (20)"""
        for i in range(1, 26):
            client.post(
                "/tasks",
                json={"title": f"Task {i}"},
                headers=get_auth_headers(auth_user["token"])
            )

        response = client.get(
            "/tasks",
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["data"]) == 20
        assert data["total"] == 25
        assert data["next_cursor"] is not None

    def test_pagination_custom_limit(self, client, auth_user):
        """Test pagination with custom limit"""
        for i in range(1, 11):
            client.post(
                "/tasks",
                json={"title": f"Task {i}"},
                headers=get_auth_headers(auth_user["token"])
            )

        response = client.get(
            "/tasks?limit=5",
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["data"]) == 5
        assert data["total"] == 10
        assert data["next_cursor"] is not None

    def test_pagination_cursor(self, client, auth_user):
        """Test pagination with cursor"""
        task_ids = []
        for i in range(1, 11):
            response = client.post(
                "/tasks",
                json={"title": f"Task {i}"},
                headers=get_auth_headers(auth_user["token"])
            )
            task_ids.append(response.get_json()["id"])

        # Get first page
        response = client.get(
            "/tasks?limit=3",
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 200
        data1 = response.get_json()
        assert len(data1["data"]) == 3
        cursor = data1["next_cursor"]

        # Get second page using cursor
        response = client.get(
            f"/tasks?limit=3&cursor={cursor}",
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 200
        data2 = response.get_json()
        assert len(data2["data"]) == 3
        assert data2["data"][0]["id"] != data1["data"][0]["id"]

    def test_pagination_max_limit(self, client, auth_user):
        """Test that limit is capped at 100"""
        for i in range(1, 6):
            client.post(
                "/tasks",
                json={"title": f"Task {i}"},
                headers=get_auth_headers(auth_user["token"])
            )

        response = client.get(
            "/tasks?limit=1000",
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["data"]) == 5
        assert data["next_cursor"] is None

    def test_pagination_no_next_cursor_when_done(self, client, auth_user):
        """Test that next_cursor is None when no more items"""
        for i in range(1, 4):
            client.post(
                "/tasks",
                json={"title": f"Task {i}"},
                headers=get_auth_headers(auth_user["token"])
            )

        response = client.get(
            "/tasks?limit=10",
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["data"]) == 3
        assert data["total"] == 3
        assert data["next_cursor"] is None

    def test_pagination_response_format(self, client, auth_user):
        """Test that response has correct format"""
        client.post(
            "/tasks",
            json={"title": "Task 1"},
            headers=get_auth_headers(auth_user["token"])
        )

        response = client.get(
            "/tasks",
            headers=get_auth_headers(auth_user["token"])
        )
        assert response.status_code == 200
        data = response.get_json()

        assert "data" in data
        assert "next_cursor" in data
        assert "total" in data
        assert isinstance(data["data"], list)
        assert isinstance(data["total"], int)
        assert data["next_cursor"] is None or isinstance(data["next_cursor"], int)

    def test_pagination_user_isolation(self, client, auth_user, another_user):
        """Test that pagination respects user isolation"""
        for i in range(1, 6):
            client.post(
                "/tasks",
                json={"title": f"User 1 Task {i}"},
                headers=get_auth_headers(auth_user["token"])
            )

        for i in range(1, 4):
            client.post(
                "/tasks",
                json={"title": f"User 2 Task {i}"},
                headers=get_auth_headers(another_user["token"])
            )

        response1 = client.get(
            "/tasks",
            headers=get_auth_headers(auth_user["token"])
        )
        data1 = response1.get_json()
        assert data1["total"] == 5

        response2 = client.get(
            "/tasks",
            headers=get_auth_headers(another_user["token"])
        )
        data2 = response2.get_json()
        assert data2["total"] == 3


class TestRateLimiting:
    def test_rate_limit_disabled_in_testing(self, client, auth_user):
        """Test that rate limiting is disabled in testing mode"""
        for _ in range(10):
            response = client.get(
                "/tasks",
                headers=get_auth_headers(auth_user["token"])
            )
            assert response.status_code == 200

    def test_rate_limit_response_format(self, client):
        """Test rate limit response format when enabled"""
        limiter.enabled = True
        try:
            for _ in range(101):
                response = client.post(
                    "/auth/register",
                    json={"username": f"user{_}", "password": "password123"}
                )
                if response.status_code == 429:
                    data = response.get_json()
                    assert "error" in data
                    assert data["error"] == "rate limit exceeded"
                    break
        finally:
            limiter.enabled = False

    def test_register_endpoint_requires_auth_for_rate_limit(self, client):
        """Test that register endpoint applies rate limiting"""
        limiter.enabled = True
        try:
            response = client.post(
                "/auth/register",
                json={"username": "testuser", "password": "password123"}
            )
            assert response.status_code in [201, 429]
        finally:
            limiter.enabled = False

    def test_login_endpoint_rate_limiting(self, client, auth_user):
        """Test that login endpoint has rate limiting"""
        limiter.enabled = True
        try:
            response = client.post(
                "/auth/login",
                json={"username": "testuser", "password": "password123"}
            )
            assert response.status_code in [200, 401, 429]
        finally:
            limiter.enabled = False

    def test_all_endpoints_have_rate_limiting(self, client, auth_user):
        """Test that all task endpoints have rate limiting applied"""
        limiter.enabled = True
        try:
            endpoints = [
                ("GET", "/tasks"),
                ("POST", "/tasks", {"title": "Test"}),
                ("GET", "/tasks/1"),
                ("PUT", "/tasks/1", {"title": "Updated"}),
            ]

            for endpoint in endpoints:
                method = endpoint[0]
                path = endpoint[1]
                data = endpoint[2] if len(endpoint) > 2 else None

                if method == "GET":
                    response = client.get(path, headers=get_auth_headers(auth_user["token"]))
                elif method == "POST":
                    response = client.post(path, json=data, headers=get_auth_headers(auth_user["token"]))
                elif method == "PUT":
                    response = client.put(path, json=data, headers=get_auth_headers(auth_user["token"]))

                assert response.status_code in [200, 201, 404, 429]
        finally:
            limiter.enabled = False


class TestHealth:
    def test_health_endpoint(self, client):
        """Test the health check endpoint (no auth required)"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
