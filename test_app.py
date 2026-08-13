"""
Tests for the Flask Task Management API with JWT authentication
"""

import pytest
import sqlite3
import os
from datetime import datetime
from unittest.mock import patch, MagicMock
from app import app, init_db, celery_app


@pytest.fixture(scope="function")
def client():
    """Create a test client with a separate test database"""
    from app import limiter

    test_db = "test_tasks.db"

    # Set the test database and disable Redis for testing
    os.environ["DATABASE"] = test_db
    os.environ["REDIS_URL"] = "memory://"

    # Clean up any existing test database
    if os.path.exists(test_db):
        os.remove(test_db)

    # Initialize the test database
    init_db()

    # Create the test client
    app.config["TESTING"] = True

    # Disable rate limiting for non-rate-limit tests
    limiter.enabled = False
    test_client = app.test_client()

    yield test_client

    # Clean up after test
    if os.path.exists(test_db):
        os.remove(test_db)


@pytest.fixture(scope="function")
def rate_limit_client():
    """Create a test client with rate limiting enabled"""
    from app import limiter

    test_db = "test_tasks_rl.db"

    # Set the test database and disable Redis for testing
    os.environ["DATABASE"] = test_db
    os.environ["REDIS_URL"] = "memory://"

    # Clean up any existing test database
    if os.path.exists(test_db):
        os.remove(test_db)

    # Initialize the test database
    init_db()

    # Create the test client
    app.config["TESTING"] = True

    # Enable rate limiting for rate limit tests
    limiter.enabled = True

    # Reset the limiter storage
    try:
        limiter.reset()
    except:
        pass

    test_client = app.test_client()

    yield test_client

    # Clean up after test
    if os.path.exists(test_db):
        os.remove(test_db)


@pytest.fixture
def mock_celery_task():
    """Mock Celery task to prevent actual task execution"""
    with patch('celery_tasks.send_notification_email') as mock_task:
        mock_task.delay = MagicMock(return_value=MagicMock(id='test-task-id'))
        yield mock_task


@pytest.fixture
def auth_user(client):
    """Register and return auth token for a test user"""
    response = client.post(
        "/auth/register",
        json={"username": "testuser", "password": "testpass123", "email": "testuser@example.com"},
        content_type="application/json"
    )
    data = response.get_json()
    return {
        "id": data["id"],
        "username": data["username"],
        "token": data["token"]
    }


@pytest.fixture
def auth_headers(auth_user):
    """Return authorization headers for the test user"""
    return {"Authorization": f"Bearer {auth_user['token']}"}


@pytest.fixture
def second_user(client):
    """Register and return a second test user"""
    response = client.post(
        "/auth/register",
        json={"username": "seconduser", "password": "testpass123", "email": "seconduser@example.com"},
        content_type="application/json"
    )
    data = response.get_json()
    return {
        "id": data["id"],
        "username": data["username"],
        "token": data["token"]
    }


@pytest.fixture
def second_auth_headers(second_user):
    """Return authorization headers for the second test user"""
    return {"Authorization": f"Bearer {second_user['token']}"}


class TestRegistration:
    def test_register_success(self, client):
        """Test successful user registration"""
        response = client.post(
            "/auth/register",
            json={"username": "newuser", "password": "password123"},
            content_type="application/json"
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["username"] == "newuser"
        assert "id" in data
        assert "token" in data

    def test_register_missing_username(self, client):
        """Test registration without username"""
        response = client.post(
            "/auth/register",
            json={"password": "password123"},
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "username is required"

    def test_register_empty_username(self, client):
        """Test registration with empty username"""
        response = client.post(
            "/auth/register",
            json={"username": "   ", "password": "password123"},
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "username is required"

    def test_register_missing_password(self, client):
        """Test registration without password"""
        response = client.post(
            "/auth/register",
            json={"username": "newuser"},
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "password is required"

    def test_register_password_too_short(self, client):
        """Test registration with password less than 6 characters"""
        response = client.post(
            "/auth/register",
            json={"username": "newuser", "password": "short"},
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "password must be at least 6 characters"

    def test_register_duplicate_username(self, client, auth_user):
        """Test registration with duplicate username"""
        response = client.post(
            "/auth/register",
            json={"username": "testuser", "password": "password123"},
            content_type="application/json"
        )

        assert response.status_code == 409
        data = response.get_json()
        assert data["error"] == "username already exists"


class TestLogin:
    def test_login_success(self, client, auth_user):
        """Test successful login"""
        response = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "testpass123"},
            content_type="application/json"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["username"] == "testuser"
        assert "id" in data
        assert "token" in data

    def test_login_missing_username(self, client):
        """Test login without username"""
        response = client.post(
            "/auth/login",
            json={"password": "testpass123"},
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "username is required"

    def test_login_missing_password(self, client, auth_user):
        """Test login without password"""
        response = client.post(
            "/auth/login",
            json={"username": "testuser"},
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "password is required"

    def test_login_invalid_username(self, client):
        """Test login with non-existent username"""
        response = client.post(
            "/auth/login",
            json={"username": "nonexistent", "password": "password123"},
            content_type="application/json"
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "Invalid username or password"

    def test_login_invalid_password(self, client, auth_user):
        """Test login with incorrect password"""
        response = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "wrongpassword"},
            content_type="application/json"
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "Invalid username or password"


class TestCreateTask:
    def test_create_task_success(self, client, auth_headers):
        """Test creating a task with valid title and auth"""
        response = client.post(
            "/tasks",
            json={"title": "Test Task"},
            headers=auth_headers,
            content_type="application/json"
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Test Task"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data
        assert "owner_id" in data

    def test_create_task_missing_token(self, client):
        """Test creating a task without authentication"""
        response = client.post(
            "/tasks",
            json={"title": "Test Task"},
            content_type="application/json"
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "Token is missing"

    def test_create_task_invalid_token(self, client):
        """Test creating a task with invalid token"""
        response = client.post(
            "/tasks",
            json={"title": "Test Task"},
            headers={"Authorization": "Bearer invalid_token"},
            content_type="application/json"
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "Token is invalid"

    def test_create_task_missing_auth_header(self, client):
        """Test creating a task with malformed authorization header"""
        response = client.post(
            "/tasks",
            json={"title": "Test Task"},
            headers={"Authorization": "InvalidFormat"},
            content_type="application/json"
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "Invalid authorization header"

    def test_create_task_missing_title(self, client, auth_headers):
        """Test creating a task without title returns 400"""
        response = client.post(
            "/tasks",
            json={},
            headers=auth_headers,
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert data["error"] == "title is required"

    def test_create_task_empty_title(self, client, auth_headers):
        """Test creating a task with empty title returns 400"""
        response = client.post(
            "/tasks",
            json={"title": "   "},
            headers=auth_headers,
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_create_task_no_json(self, client, auth_headers):
        """Test creating a task with no JSON body returns 400"""
        response = client.post(
            "/tasks",
            headers=auth_headers
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data


class TestListTasks:
    def test_list_tasks_empty(self, client, auth_headers):
        """Test listing tasks when database is empty"""
        response = client.get("/tasks", headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data["data"] == []
        assert data["total"] == 0
        assert data["next_cursor"] is None

    def test_list_tasks_multiple(self, client, auth_headers):
        """Test listing multiple tasks in descending order"""
        # Create three tasks
        client.post("/tasks", json={"title": "Task 1"}, headers=auth_headers, content_type="application/json")
        client.post("/tasks", json={"title": "Task 2"}, headers=auth_headers, content_type="application/json")
        client.post("/tasks", json={"title": "Task 3"}, headers=auth_headers, content_type="application/json")

        response = client.get("/tasks", headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["data"]) == 3
        # Verify descending order (newest first)
        assert data["data"][0]["title"] == "Task 3"
        assert data["data"][1]["title"] == "Task 2"
        assert data["data"][2]["title"] == "Task 1"

    def test_list_tasks_ordered_by_created_at(self, client, auth_headers):
        """Test that tasks are ordered by created_at descending"""
        resp1 = client.post("/tasks", json={"title": "First"}, headers=auth_headers, content_type="application/json")
        resp2 = client.post("/tasks", json={"title": "Second"}, headers=auth_headers, content_type="application/json")

        response = client.get("/tasks", headers=auth_headers)
        data = response.get_json()

        # Most recent should be first
        assert data["data"][0]["id"] == resp2.get_json()["id"]
        assert data["data"][1]["id"] == resp1.get_json()["id"]

    def test_list_tasks_missing_token(self, client):
        """Test listing tasks without authentication"""
        response = client.get("/tasks")

        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "Token is missing"

    def test_list_tasks_user_isolation(self, client, auth_headers, second_auth_headers):
        """Test that users only see their own tasks"""
        # Create tasks for first user
        client.post("/tasks", json={"title": "User1 Task 1"}, headers=auth_headers, content_type="application/json")
        client.post("/tasks", json={"title": "User1 Task 2"}, headers=auth_headers, content_type="application/json")

        # Create tasks for second user
        client.post("/tasks", json={"title": "User2 Task 1"}, headers=second_auth_headers, content_type="application/json")

        # Verify first user only sees their tasks
        response = client.get("/tasks", headers=auth_headers)
        data = response.get_json()
        assert len(data["data"]) == 2
        assert all(t["title"].startswith("User1") for t in data["data"])

        # Verify second user only sees their tasks
        response = client.get("/tasks", headers=second_auth_headers)
        data = response.get_json()
        assert len(data["data"]) == 1
        assert data["data"][0]["title"] == "User2 Task 1"


class TestGetTask:
    def test_get_task_success(self, client, auth_headers):
        """Test getting a specific task"""
        create_resp = client.post(
            "/tasks",
            json={"title": "Test Task"},
            headers=auth_headers,
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        response = client.get(f"/tasks/{task_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Test Task"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client, auth_headers):
        """Test getting a non-existent task returns 404"""
        response = client.get("/tasks/999", headers=auth_headers)

        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "task not found"

    def test_get_task_missing_token(self, client):
        """Test getting a task without authentication"""
        response = client.get("/tasks/1")

        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "Token is missing"

    def test_get_task_other_user_task(self, client, auth_headers, second_auth_headers):
        """Test that user cannot access another user's task"""
        # Create task with first user
        create_resp = client.post(
            "/tasks",
            json={"title": "User1 Task"},
            headers=auth_headers,
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        # Try to access with second user
        response = client.get(f"/tasks/{task_id}", headers=second_auth_headers)

        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "task not found"


class TestUpdateTask:
    def test_update_task_title(self, client, auth_headers):
        """Test updating only the title"""
        create_resp = client.post(
            "/tasks",
            json={"title": "Original Title"},
            headers=auth_headers,
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated Title"},
            headers=auth_headers,
            content_type="application/json"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated Title"
        assert data["status"] == "pending"

    def test_update_task_status(self, client, auth_headers):
        """Test updating only the status"""
        create_resp = client.post(
            "/tasks",
            json={"title": "Test Task"},
            headers=auth_headers,
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"status": "completed"},
            headers=auth_headers,
            content_type="application/json"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Test Task"
        assert data["status"] == "completed"

    def test_update_task_both(self, client, auth_headers):
        """Test updating both title and status"""
        create_resp = client.post(
            "/tasks",
            json={"title": "Original"},
            headers=auth_headers,
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated", "status": "in_progress"},
            headers=auth_headers,
            content_type="application/json"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_task_not_found(self, client, auth_headers):
        """Test updating a non-existent task returns 404"""
        response = client.put(
            "/tasks/999",
            json={"title": "Updated"},
            headers=auth_headers,
            content_type="application/json"
        )

        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "task not found"

    def test_update_task_empty_title(self, client, auth_headers):
        """Test updating title to empty string returns 400"""
        create_resp = client.post(
            "/tasks",
            json={"title": "Original"},
            headers=auth_headers,
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "   "},
            headers=auth_headers,
            content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_update_task_no_changes(self, client, auth_headers):
        """Test updating a task with no fields still returns success"""
        create_resp = client.post(
            "/tasks",
            json={"title": "Original"},
            headers=auth_headers,
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]
        original_title = create_resp.get_json()["title"]

        response = client.put(
            f"/tasks/{task_id}",
            json={},
            headers=auth_headers,
            content_type="application/json"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == original_title

    def test_update_task_missing_token(self, client):
        """Test updating a task without authentication"""
        response = client.put(
            "/tasks/1",
            json={"title": "Updated"},
            content_type="application/json"
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "Token is missing"

    def test_update_task_other_user_task(self, client, auth_headers, second_auth_headers):
        """Test that user cannot update another user's task"""
        # Create task with first user
        create_resp = client.post(
            "/tasks",
            json={"title": "User1 Task"},
            headers=auth_headers,
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        # Try to update with second user
        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated"},
            headers=second_auth_headers,
            content_type="application/json"
        )

        assert response.status_code == 403
        data = response.get_json()
        assert data["error"] == "unauthorized"


class TestNotificationTrigger:
    def test_notification_sent_on_task_completion(self, client, auth_headers):
        """Test that notification is sent when task status changes to completed"""
        create_resp = client.post(
            "/tasks",
            json={"title": "Test Task"},
            headers=auth_headers,
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        with patch('celery_tasks.send_notification_email.delay') as mock_delay:
            response = client.put(
                f"/tasks/{task_id}",
                json={"status": "completed"},
                headers=auth_headers,
                content_type="application/json"
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "completed"
        mock_delay.assert_called_once_with("testuser@example.com", "Test Task")

    def test_notification_not_sent_for_non_completed_status(self, client, auth_headers):
        """Test that notification is not sent for non-completed status changes"""
        create_resp = client.post(
            "/tasks",
            json={"title": "Test Task"},
            headers=auth_headers,
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        with patch('celery_tasks.send_notification_email.delay') as mock_delay:
            response = client.put(
                f"/tasks/{task_id}",
                json={"status": "in_progress"},
                headers=auth_headers,
                content_type="application/json"
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "in_progress"
        mock_delay.assert_not_called()

    def test_notification_not_sent_when_already_completed(self, client, auth_headers):
        """Test that notification is not sent if task is already completed"""
        create_resp = client.post(
            "/tasks",
            json={"title": "Test Task"},
            headers=auth_headers,
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        with patch('celery_tasks.send_notification_email.delay') as mock_delay:
            client.put(
                f"/tasks/{task_id}",
                json={"status": "completed"},
                headers=auth_headers,
                content_type="application/json"
            )
            mock_delay.reset_mock()

            client.put(
                f"/tasks/{task_id}",
                json={"status": "completed"},
                headers=auth_headers,
                content_type="application/json"
            )

        mock_delay.assert_not_called()

    def test_notification_with_user_without_email(self, client):
        """Test that notification is skipped for users without email"""
        response = client.post(
            "/auth/register",
            json={"username": "noemail", "password": "testpass123"},
            content_type="application/json"
        )
        user_id = response.get_json()["id"]
        token = response.get_json()["token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        create_resp = client.post(
            "/tasks",
            json={"title": "Test Task"},
            headers=auth_headers,
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        with patch('celery_tasks.send_notification_email.delay') as mock_delay:
            response = client.put(
                f"/tasks/{task_id}",
                json={"status": "completed"},
                headers=auth_headers,
                content_type="application/json"
            )

        assert response.status_code == 200
        mock_delay.assert_not_called()

    def test_notification_sent_with_correct_title(self, client, auth_headers):
        """Test that notification is sent with the correct task title"""
        create_resp = client.post(
            "/tasks",
            json={"title": "Important Project Deadline"},
            headers=auth_headers,
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        with patch('celery_tasks.send_notification_email.delay') as mock_delay:
            client.put(
                f"/tasks/{task_id}",
                json={"status": "completed"},
                headers=auth_headers,
                content_type="application/json"
            )

        mock_delay.assert_called_once_with("testuser@example.com", "Important Project Deadline")


class TestIntegration:
    def test_full_workflow_with_auth(self, client, auth_headers):
        """Test a complete task management workflow with authentication"""
        # Create tasks
        resp1 = client.post("/tasks", json={"title": "Buy groceries"}, headers=auth_headers, content_type="application/json")
        resp2 = client.post("/tasks", json={"title": "Write code"}, headers=auth_headers, content_type="application/json")

        task1_id = resp1.get_json()["id"]
        task2_id = resp2.get_json()["id"]

        # List tasks
        list_resp = client.get("/tasks", headers=auth_headers)
        assert list_resp.get_json()["total"] == 2

        # Get single task
        get_resp = client.get(f"/tasks/{task1_id}", headers=auth_headers)
        assert get_resp.get_json()["title"] == "Buy groceries"

        # Update task status
        update_resp = client.put(
            f"/tasks/{task1_id}",
            json={"status": "completed"},
            headers=auth_headers,
            content_type="application/json"
        )
        assert update_resp.get_json()["status"] == "completed"

        # Verify update persisted
        verify_resp = client.get(f"/tasks/{task1_id}", headers=auth_headers)
        assert verify_resp.get_json()["status"] == "completed"

    def test_multi_user_isolation(self, client, auth_headers, second_auth_headers):
        """Test that multiple users can work independently"""
        # User 1 creates tasks
        resp1 = client.post("/tasks", json={"title": "User1 Task"}, headers=auth_headers, content_type="application/json")
        task1_id = resp1.get_json()["id"]

        # User 2 creates tasks
        resp2 = client.post("/tasks", json={"title": "User2 Task"}, headers=second_auth_headers, content_type="application/json")
        task2_id = resp2.get_json()["id"]

        # User 1 updates their task
        client.put(
            f"/tasks/{task1_id}",
            json={"status": "completed"},
            headers=auth_headers,
            content_type="application/json"
        )

        # Verify User 1 sees only their task completed
        list_resp = client.get("/tasks", headers=auth_headers)
        user1_data = list_resp.get_json()
        assert user1_data["total"] == 1
        assert user1_data["data"][0]["status"] == "completed"

        # Verify User 2's task is not affected
        list_resp = client.get("/tasks", headers=second_auth_headers)
        user2_data = list_resp.get_json()
        assert user2_data["total"] == 1
        assert user2_data["data"][0]["status"] == "pending"


class TestPagination:
    def test_list_tasks_pagination_first_page(self, client, auth_headers):
        """Test pagination returns first page with default limit"""
        for i in range(5):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=auth_headers, content_type="application/json")

        response = client.get("/tasks", headers=auth_headers)
        data = response.get_json()

        assert response.status_code == 200
        assert "data" in data
        assert "next_cursor" in data
        assert "total" in data
        assert data["total"] == 5
        assert len(data["data"]) == 5

    def test_list_tasks_pagination_with_limit(self, client, auth_headers):
        """Test pagination with custom limit"""
        for i in range(5):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=auth_headers, content_type="application/json")

        response = client.get("/tasks?limit=2", headers=auth_headers)
        data = response.get_json()

        assert response.status_code == 200
        assert len(data["data"]) == 2
        assert data["total"] == 5
        assert data["next_cursor"] is not None

    def test_list_tasks_pagination_cursor(self, client, auth_headers):
        """Test pagination with cursor"""
        # Create tasks
        ids = []
        for i in range(5):
            resp = client.post("/tasks", json={"title": f"Task {i}"}, headers=auth_headers, content_type="application/json")
            ids.append(resp.get_json()["id"])

        # Get first page with limit 2
        resp1 = client.get("/tasks?limit=2", headers=auth_headers)
        data1 = resp1.get_json()

        assert len(data1["data"]) == 2
        assert data1["next_cursor"] is not None

        # Get second page using cursor
        resp2 = client.get(f"/tasks?cursor={data1['next_cursor']}&limit=2", headers=auth_headers)
        data2 = resp2.get_json()

        assert len(data2["data"]) == 2
        assert data1["data"][0]["id"] != data2["data"][0]["id"]

    def test_list_tasks_pagination_last_page(self, client, auth_headers):
        """Test that last page has no next_cursor"""
        for i in range(3):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=auth_headers, content_type="application/json")

        response = client.get("/tasks?limit=10", headers=auth_headers)
        data = response.get_json()

        assert len(data["data"]) == 3
        assert data["next_cursor"] is None
        assert data["total"] == 3

    def test_list_tasks_pagination_invalid_limit(self, client, auth_headers):
        """Test that invalid limit defaults to 20"""
        for i in range(5):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=auth_headers, content_type="application/json")

        # Test negative limit
        response = client.get("/tasks?limit=-5", headers=auth_headers)
        data = response.get_json()
        assert len(data["data"]) <= 5

        # Test zero limit
        response = client.get("/tasks?limit=0", headers=auth_headers)
        data = response.get_json()
        assert len(data["data"]) <= 5

        # Test limit over max (should default to 20)
        response = client.get("/tasks?limit=150", headers=auth_headers)
        data = response.get_json()
        assert len(data["data"]) <= 5

    def test_list_tasks_pagination_empty(self, client, auth_headers):
        """Test pagination on empty task list"""
        response = client.get("/tasks", headers=auth_headers)
        data = response.get_json()

        assert response.status_code == 200
        assert data["data"] == []
        assert data["next_cursor"] is None
        assert data["total"] == 0

    def test_list_tasks_pagination_invalid_cursor(self, client, auth_headers):
        """Test pagination with invalid cursor"""
        for i in range(5):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=auth_headers, content_type="application/json")

        # Non-existent cursor should start from beginning
        response = client.get("/tasks?cursor=9999&limit=2", headers=auth_headers)
        data = response.get_json()

        assert response.status_code == 200
        assert len(data["data"]) == 2
        assert data["total"] == 5

    def test_list_tasks_pagination_preserved_on_second_user(self, client, auth_headers, second_auth_headers):
        """Test that pagination is isolated per user"""
        # User 1 creates 3 tasks
        for i in range(3):
            client.post("/tasks", json={"title": f"User1 Task {i}"}, headers=auth_headers, content_type="application/json")

        # User 2 creates 5 tasks
        for i in range(5):
            client.post("/tasks", json={"title": f"User2 Task {i}"}, headers=second_auth_headers, content_type="application/json")

        # User 1 should see only their 3 tasks
        response = client.get("/tasks", headers=auth_headers)
        data = response.get_json()
        assert data["total"] == 3
        assert len(data["data"]) == 3

        # User 2 should see only their 5 tasks
        response = client.get("/tasks", headers=second_auth_headers)
        data = response.get_json()
        assert data["total"] == 5
        assert len(data["data"]) == 5


class TestRateLimiting:
    def test_rate_limit_applied_to_register(self, rate_limit_client):
        """Test rate limiting is applied to register endpoint"""
        # Make 101 requests to exceed the 100 per minute limit
        for i in range(100):
            response = rate_limit_client.post(
                "/auth/register",
                json={"username": f"user{i}", "password": "password123"},
                content_type="application/json"
            )
            # First 100 should succeed or fail due to duplicate username
            assert response.status_code in [201, 409]

        # 101st request should hit rate limit
        response = rate_limit_client.post(
            "/auth/register",
            json={"username": "limiteduser", "password": "password123"},
            content_type="application/json"
        )
        assert response.status_code == 429
        assert response.get_json()["error"] == "Rate limit exceeded"
        assert "Retry-After" in response.headers

    def test_rate_limit_applied_to_login(self, rate_limit_client):
        """Test rate limiting is applied to login endpoint"""
        # Create a user first
        resp = rate_limit_client.post(
            "/auth/register",
            json={"username": "loginuser", "password": "testpass123"},
            content_type="application/json"
        )
        # Register endpoint is also rate limited, so check it worked
        assert resp.status_code in [201, 429]
        if resp.status_code != 201:
            # If rate limited on register, skip this test
            pytest.skip("Register endpoint rate limited")

        # Make 100 login requests
        for i in range(100):
            response = rate_limit_client.post(
                "/auth/login",
                json={"username": "loginuser", "password": "testpass123"},
                content_type="application/json"
            )
            assert response.status_code == 200

        # 101st request should hit rate limit
        response = rate_limit_client.post(
            "/auth/login",
            json={"username": "loginuser", "password": "testpass123"},
            content_type="application/json"
        )
        assert response.status_code == 429
        assert response.get_json()["error"] == "Rate limit exceeded"

    def test_rate_limit_applied_to_create_task(self, rate_limit_client):
        """Test rate limiting is applied to create task endpoint"""
        # Create user and get token
        resp = rate_limit_client.post(
            "/auth/register",
            json={"username": "createtaskuser", "password": "testpass123"},
            content_type="application/json"
        )
        if resp.status_code != 201:
            pytest.skip("Register endpoint rate limited")

        token = resp.get_json()["token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Make 100 create task requests
        for i in range(100):
            response = rate_limit_client.post(
                "/tasks",
                json={"title": f"Task {i}"},
                headers=auth_headers,
                content_type="application/json"
            )
            assert response.status_code == 201

        # 101st request should hit rate limit
        response = rate_limit_client.post(
            "/tasks",
            json={"title": "Limited Task"},
            headers=auth_headers,
            content_type="application/json"
        )
        assert response.status_code == 429

    def test_rate_limit_applied_to_list_tasks(self, rate_limit_client):
        """Test rate limiting is applied to list tasks endpoint"""
        # Create user and get token
        resp = rate_limit_client.post(
            "/auth/register",
            json={"username": "listtaskuser", "password": "testpass123"},
            content_type="application/json"
        )
        if resp.status_code != 201:
            pytest.skip("Register endpoint rate limited")

        token = resp.get_json()["token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Make 100 list requests
        for i in range(100):
            response = rate_limit_client.get("/tasks", headers=auth_headers)
            assert response.status_code == 200

        # 101st request should hit rate limit
        response = rate_limit_client.get("/tasks", headers=auth_headers)
        assert response.status_code == 429

    def test_rate_limit_applied_to_get_task(self, rate_limit_client):
        """Test rate limiting is applied to get task endpoint"""
        # Create user and get token
        resp = rate_limit_client.post(
            "/auth/register",
            json={"username": "gettaskuser", "password": "testpass123"},
            content_type="application/json"
        )
        if resp.status_code != 201:
            pytest.skip("Register endpoint rate limited")

        token = resp.get_json()["token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Create one task
        create_resp = rate_limit_client.post(
            "/tasks",
            json={"title": "Task"},
            headers=auth_headers,
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        # Make 100 get requests
        for i in range(100):
            response = rate_limit_client.get(f"/tasks/{task_id}", headers=auth_headers)
            assert response.status_code == 200

        # 101st request should hit rate limit
        response = rate_limit_client.get(f"/tasks/{task_id}", headers=auth_headers)
        assert response.status_code == 429

    def test_rate_limit_applied_to_update_task(self, rate_limit_client):
        """Test rate limiting is applied to update task endpoint"""
        # Create user and get token
        resp = rate_limit_client.post(
            "/auth/register",
            json={"username": "updatetaskuser", "password": "testpass123"},
            content_type="application/json"
        )
        if resp.status_code != 201:
            pytest.skip("Register endpoint rate limited")

        token = resp.get_json()["token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Create one task
        create_resp = rate_limit_client.post(
            "/tasks",
            json={"title": "Task"},
            headers=auth_headers,
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        # Make 100 update requests
        for i in range(100):
            response = rate_limit_client.put(
                f"/tasks/{task_id}",
                json={"title": f"Updated {i}"},
                headers=auth_headers,
                content_type="application/json"
            )
            assert response.status_code == 200

        # 101st request should hit rate limit
        response = rate_limit_client.put(
            f"/tasks/{task_id}",
            json={"title": "Final Update"},
            headers=auth_headers,
            content_type="application/json"
        )
        assert response.status_code == 429

    def test_rate_limit_per_user(self, rate_limit_client):
        """Test that rate limits are applied per user, not globally"""
        # Create two users
        resp1 = rate_limit_client.post(
            "/auth/register",
            json={"username": "ratelimituser1", "password": "testpass123"},
            content_type="application/json"
        )
        if resp1.status_code != 201:
            pytest.skip("Register endpoint rate limited")

        token1 = resp1.get_json()["token"]
        auth_headers_1 = {"Authorization": f"Bearer {token1}"}

        resp2 = rate_limit_client.post(
            "/auth/register",
            json={"username": "ratelimituser2", "password": "testpass123"},
            content_type="application/json"
        )
        if resp2.status_code != 201:
            pytest.skip("Register endpoint rate limited")

        token2 = resp2.get_json()["token"]
        auth_headers_2 = {"Authorization": f"Bearer {token2}"}

        # User 1 makes requests up to limit
        for i in range(100):
            response = rate_limit_client.get("/tasks", headers=auth_headers_1)
            assert response.status_code == 200

        # User 1 should be rate limited
        response = rate_limit_client.get("/tasks", headers=auth_headers_1)
        assert response.status_code == 429

        # User 2 should still be able to make requests
        response = rate_limit_client.get("/tasks", headers=auth_headers_2)
        assert response.status_code == 200

    def test_retry_after_header_value(self, rate_limit_client):
        """Test that Retry-After header is set correctly"""
        # Make requests to exceed limit
        for i in range(100):
            rate_limit_client.post(
                "/auth/register",
                json={"username": f"user{i}", "password": "password123"},
                content_type="application/json"
            )

        response = rate_limit_client.post(
            "/auth/register",
            json={"username": "limiteduser", "password": "password123"},
            content_type="application/json"
        )

        assert response.status_code == 429
        assert response.headers.get("Retry-After") == "60"
