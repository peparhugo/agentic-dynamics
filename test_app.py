"""
Tests for the Flask Task Management API with JWT authentication
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


@pytest.fixture
def auth_user(client):
    """Register and return auth token for a test user"""
    response = client.post(
        "/auth/register",
        json={"username": "testuser", "password": "testpass123"},
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
        json={"username": "seconduser", "password": "testpass123"},
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
        assert data == []

    def test_list_tasks_multiple(self, client, auth_headers):
        """Test listing multiple tasks in descending order"""
        # Create three tasks
        client.post("/tasks", json={"title": "Task 1"}, headers=auth_headers, content_type="application/json")
        client.post("/tasks", json={"title": "Task 2"}, headers=auth_headers, content_type="application/json")
        client.post("/tasks", json={"title": "Task 3"}, headers=auth_headers, content_type="application/json")

        response = client.get("/tasks", headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 3
        # Verify descending order (newest first)
        assert data[0]["title"] == "Task 3"
        assert data[1]["title"] == "Task 2"
        assert data[2]["title"] == "Task 1"

    def test_list_tasks_ordered_by_created_at(self, client, auth_headers):
        """Test that tasks are ordered by created_at descending"""
        resp1 = client.post("/tasks", json={"title": "First"}, headers=auth_headers, content_type="application/json")
        resp2 = client.post("/tasks", json={"title": "Second"}, headers=auth_headers, content_type="application/json")

        response = client.get("/tasks", headers=auth_headers)
        data = response.get_json()

        # Most recent should be first
        assert data[0]["id"] == resp2.get_json()["id"]
        assert data[1]["id"] == resp1.get_json()["id"]

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
        assert len(data) == 2
        assert all(t["title"].startswith("User1") for t in data)

        # Verify second user only sees their tasks
        response = client.get("/tasks", headers=second_auth_headers)
        data = response.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "User2 Task 1"


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
        assert len(list_resp.get_json()) == 2

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
        user1_tasks = list_resp.get_json()
        assert len(user1_tasks) == 1
        assert user1_tasks[0]["status"] == "completed"

        # Verify User 2's task is not affected
        list_resp = client.get("/tasks", headers=second_auth_headers)
        user2_tasks = list_resp.get_json()
        assert len(user2_tasks) == 1
        assert user2_tasks[0]["status"] == "pending"
