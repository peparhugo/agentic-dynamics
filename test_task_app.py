"""
Tests for the Flask Task Management API with JWT Authentication
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
    with app.test_client() as test_client:
        yield test_client

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
        assert data == []

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
        assert len(data) == 1
        assert data[0]["title"] == "User 1 Task"

        # User 2 lists tasks - should only see their own
        response = client.get(
            "/tasks",
            headers=get_auth_headers(another_user["token"])
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "User 2 Task"

    def test_list_tasks_ordered_by_created_at_desc(self, client, auth_user):
        """Test that tasks are listed in descending order by created_at"""
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
        assert len(data) == 3

        # Should be in reverse order (most recent first)
        assert data[0]["title"] == "Task 3"
        assert data[1]["title"] == "Task 2"
        assert data[2]["title"] == "Task 1"


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
        tasks = response.get_json()
        assert len(tasks) == 2
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
        tasks = response.get_json()
        assert len(tasks) == 3
        assert all("User 1" in t["title"] for t in tasks)

        # Verify User 2 sees only 2 tasks
        response = client.get(
            "/tasks",
            headers=get_auth_headers(another_user["token"])
        )
        tasks = response.get_json()
        assert len(tasks) == 2
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


class TestHealth:
    def test_health_endpoint(self, client):
        """Test the health check endpoint (no auth required)"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
