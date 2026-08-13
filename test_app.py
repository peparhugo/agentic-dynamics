"""
Comprehensive tests for the Flask task management API with authentication.
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


@pytest.fixture
def registered_user(client):
    """Create a registered user and return username/password/token."""
    username = "testuser"
    password = "testpass123"

    response = client.post(
        "/auth/register",
        json={"username": username, "password": password},
        content_type="application/json"
    )
    assert response.status_code == 201

    # Login to get token
    login_response = client.post(
        "/auth/login",
        json={"username": username, "password": password},
        content_type="application/json"
    )
    assert login_response.status_code == 200
    token = login_response.get_json()["token"]
    user_id = login_response.get_json()["user_id"]

    return {
        "username": username,
        "password": password,
        "token": token,
        "user_id": user_id,
    }


class TestAuthRegister:
    def test_register_success(self, client):
        """Test successfully registering a user."""
        response = client.post(
            "/auth/register",
            json={"username": "newuser", "password": "password123"},
            content_type="application/json"
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["username"] == "newuser"
        assert "id" in data
        assert "password_hash" not in data  # Password hash should not be exposed

    def test_register_missing_username(self, client):
        """Test register without username returns 400."""
        response = client.post(
            "/auth/register",
            json={"password": "password123"},
            content_type="application/json"
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_register_missing_password(self, client):
        """Test register without password returns 400."""
        response = client.post(
            "/auth/register",
            json={"username": "newuser"},
            content_type="application/json"
        )
        assert response.status_code == 400

    def test_register_duplicate_username(self, client):
        """Test registering with duplicate username returns 400."""
        # Register first user
        client.post(
            "/auth/register",
            json={"username": "duplicate", "password": "pass1"},
            content_type="application/json"
        )

        # Try to register with same username
        response = client.post(
            "/auth/register",
            json={"username": "duplicate", "password": "pass2"},
            content_type="application/json"
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "already exists" in data["error"]

    def test_register_empty_username(self, client):
        """Test registering with empty username returns 400."""
        response = client.post(
            "/auth/register",
            json={"username": "   ", "password": "password123"},
            content_type="application/json"
        )
        assert response.status_code == 400

    def test_register_empty_password(self, client):
        """Test registering with empty password returns 400."""
        response = client.post(
            "/auth/register",
            json={"username": "newuser", "password": "   "},
            content_type="application/json"
        )
        assert response.status_code == 400


class TestAuthLogin:
    def test_login_success(self, client, registered_user):
        """Test successfully logging in returns JWT token."""
        response = client.post(
            "/auth/login",
            json={"username": registered_user["username"], "password": registered_user["password"]},
            content_type="application/json"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "token" in data
        assert "user_id" in data
        assert data["username"] == registered_user["username"]
        # Token should be a valid JWT (not comparing actual value as exp claim changes)
        assert isinstance(data["token"], str)
        assert len(data["token"]) > 0

    def test_login_wrong_password(self, client, registered_user):
        """Test login with wrong password returns 401."""
        response = client.post(
            "/auth/login",
            json={"username": registered_user["username"], "password": "wrongpassword"},
            content_type="application/json"
        )
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_login_nonexistent_user(self, client):
        """Test login with nonexistent user returns 401."""
        response = client.post(
            "/auth/login",
            json={"username": "nonexistent", "password": "password"},
            content_type="application/json"
        )
        assert response.status_code == 401

    def test_login_missing_username(self, client):
        """Test login without username returns 400."""
        response = client.post(
            "/auth/login",
            json={"password": "password123"},
            content_type="application/json"
        )
        assert response.status_code == 400

    def test_login_missing_password(self, client):
        """Test login without password returns 400."""
        response = client.post(
            "/auth/login",
            json={"username": "user"},
            content_type="application/json"
        )
        assert response.status_code == 400


class TestCreateTask:
    def test_create_task_success(self, client, registered_user):
        """Test successfully creating a task requires auth."""
        response = client.post(
            "/tasks",
            json={"title": "Test task"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Test task"
        assert data["status"] == "pending"
        assert data["owner_id"] == registered_user["user_id"]
        assert "id" in data
        assert "created_at" in data

    def test_create_task_missing_auth(self, client):
        """Test creating a task without auth returns 401."""
        response = client.post(
            "/tasks",
            json={"title": "Test task"},
            content_type="application/json"
        )
        assert response.status_code == 401

    def test_create_task_invalid_token(self, client):
        """Test creating a task with invalid token returns 401."""
        response = client.post(
            "/tasks",
            json={"title": "Test task"},
            headers={"Authorization": "Bearer invalid_token"},
            content_type="application/json"
        )
        assert response.status_code == 401

    def test_create_task_missing_title(self, client, registered_user):
        """Test creating a task without a title returns 400."""
        response = client.post(
            "/tasks",
            json={},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_create_task_empty_title(self, client, registered_user):
        """Test creating a task with empty title returns 400."""
        response = client.post(
            "/tasks",
            json={"title": "   "},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        assert response.status_code == 400

    def test_create_task_status_default_pending(self, client, registered_user):
        """Test that created task has status 'pending' by default."""
        response = client.post(
            "/tasks",
            json={"title": "New task"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        data = response.get_json()
        assert data["status"] == "pending"


class TestListTasks:
    def test_list_empty(self, client, registered_user):
        """Test listing tasks when none exist."""
        response = client.get(
            "/tasks",
            headers={"Authorization": f"Bearer {registered_user['token']}"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_list_tasks_missing_auth(self, client):
        """Test listing tasks without auth returns 401."""
        response = client.get("/tasks")
        assert response.status_code == 401

    def test_list_tasks_invalid_token(self, client):
        """Test listing tasks with invalid token returns 401."""
        response = client.get(
            "/tasks",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401

    def test_list_tasks_ordered_by_created_at_desc(self, client, registered_user):
        """Test that tasks are returned in reverse chronological order."""
        # Create multiple tasks
        client.post(
            "/tasks",
            json={"title": "First"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        client.post(
            "/tasks",
            json={"title": "Second"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        client.post(
            "/tasks",
            json={"title": "Third"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )

        response = client.get(
            "/tasks",
            headers={"Authorization": f"Bearer {registered_user['token']}"}
        )
        assert response.status_code == 200
        data = response.get_json()

        assert len(data) == 3
        # Should be in reverse order (newest first)
        assert data[0]["title"] == "Third"
        assert data[1]["title"] == "Second"
        assert data[2]["title"] == "First"

    def test_list_tasks_only_own_tasks(self, client):
        """Test that users only see their own tasks."""
        # Register and create tasks for user 1
        user1_response = client.post(
            "/auth/register",
            json={"username": "user1", "password": "pass1"},
            content_type="application/json"
        )
        user1_id = user1_response.get_json()["id"]

        login1 = client.post(
            "/auth/login",
            json={"username": "user1", "password": "pass1"},
            content_type="application/json"
        )
        token1 = login1.get_json()["token"]

        # Create a task for user 1
        client.post(
            "/tasks",
            json={"title": "User 1 Task"},
            headers={"Authorization": f"Bearer {token1}"},
            content_type="application/json"
        )

        # Register and create tasks for user 2
        user2_response = client.post(
            "/auth/register",
            json={"username": "user2", "password": "pass2"},
            content_type="application/json"
        )
        user2_id = user2_response.get_json()["id"]

        login2 = client.post(
            "/auth/login",
            json={"username": "user2", "password": "pass2"},
            content_type="application/json"
        )
        token2 = login2.get_json()["token"]

        # Create a task for user 2
        client.post(
            "/tasks",
            json={"title": "User 2 Task"},
            headers={"Authorization": f"Bearer {token2}"},
            content_type="application/json"
        )

        # User 1 should only see their task
        response1 = client.get(
            "/tasks",
            headers={"Authorization": f"Bearer {token1}"}
        )
        data1 = response1.get_json()
        assert len(data1) == 1
        assert data1[0]["title"] == "User 1 Task"
        assert data1[0]["owner_id"] == user1_id

        # User 2 should only see their task
        response2 = client.get(
            "/tasks",
            headers={"Authorization": f"Bearer {token2}"}
        )
        data2 = response2.get_json()
        assert len(data2) == 1
        assert data2[0]["title"] == "User 2 Task"
        assert data2[0]["owner_id"] == user2_id


class TestGetTask:
    def test_get_task_success(self, client, registered_user):
        """Test retrieving a single task."""
        create_resp = client.post(
            "/tasks",
            json={"title": "Get me"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        response = client.get(
            f"/tasks/{task_id}",
            headers={"Authorization": f"Bearer {registered_user['token']}"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Get me"
        assert data["status"] == "pending"
        assert data["owner_id"] == registered_user["user_id"]

    def test_get_task_missing_auth(self, client):
        """Test getting a task without auth returns 401."""
        response = client.get("/tasks/1")
        assert response.status_code == 401

    def test_get_task_not_found(self, client, registered_user):
        """Test retrieving a non-existent task returns 404."""
        response = client.get(
            "/tasks/9999",
            headers={"Authorization": f"Bearer {registered_user['token']}"}
        )
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_get_other_user_task(self, client):
        """Test that users cannot access other users' tasks."""
        # Create user 1 and task
        client.post(
            "/auth/register",
            json={"username": "user1", "password": "pass1"},
            content_type="application/json"
        )
        login1 = client.post(
            "/auth/login",
            json={"username": "user1", "password": "pass1"},
            content_type="application/json"
        )
        token1 = login1.get_json()["token"]

        create_resp = client.post(
            "/tasks",
            json={"title": "User 1 Task"},
            headers={"Authorization": f"Bearer {token1}"},
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        # Create user 2
        client.post(
            "/auth/register",
            json={"username": "user2", "password": "pass2"},
            content_type="application/json"
        )
        login2 = client.post(
            "/auth/login",
            json={"username": "user2", "password": "pass2"},
            content_type="application/json"
        )
        token2 = login2.get_json()["token"]

        # User 2 tries to get user 1's task
        response = client.get(
            f"/tasks/{task_id}",
            headers={"Authorization": f"Bearer {token2}"}
        )
        assert response.status_code == 404


class TestUpdateTask:
    def test_update_task_title(self, client, registered_user):
        """Test updating task title."""
        create_resp = client.post(
            "/tasks",
            json={"title": "Original"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "pending"

    def test_update_task_status(self, client, registered_user):
        """Test updating task status."""
        create_resp = client.post(
            "/tasks",
            json={"title": "Task"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"status": "completed"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "completed"
        assert data["title"] == "Task"

    def test_update_task_title_and_status(self, client, registered_user):
        """Test updating both title and status."""
        create_resp = client.post(
            "/tasks",
            json={"title": "Original"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated", "status": "in_progress"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_task_missing_auth(self, client):
        """Test updating a task without auth returns 401."""
        response = client.put(
            "/tasks/1",
            json={"title": "New title"},
            content_type="application/json"
        )
        assert response.status_code == 401

    def test_update_task_not_found(self, client, registered_user):
        """Test updating a non-existent task returns 404."""
        response = client.put(
            "/tasks/9999",
            json={"title": "New title"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        assert response.status_code == 404

    def test_update_other_user_task(self, client):
        """Test that users cannot update other users' tasks."""
        # Create user 1 and task
        client.post(
            "/auth/register",
            json={"username": "user1", "password": "pass1"},
            content_type="application/json"
        )
        login1 = client.post(
            "/auth/login",
            json={"username": "user1", "password": "pass1"},
            content_type="application/json"
        )
        token1 = login1.get_json()["token"]

        create_resp = client.post(
            "/tasks",
            json={"title": "User 1 Task"},
            headers={"Authorization": f"Bearer {token1}"},
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]

        # Create user 2
        client.post(
            "/auth/register",
            json={"username": "user2", "password": "pass2"},
            content_type="application/json"
        )
        login2 = client.post(
            "/auth/login",
            json={"username": "user2", "password": "pass2"},
            content_type="application/json"
        )
        token2 = login2.get_json()["token"]

        # User 2 tries to update user 1's task
        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Hacked"},
            headers={"Authorization": f"Bearer {token2}"},
            content_type="application/json"
        )
        assert response.status_code == 404

    def test_update_task_empty_body(self, client, registered_user):
        """Test updating with empty body (no changes)."""
        create_resp = client.post(
            "/tasks",
            json={"title": "Original"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]
        original = create_resp.get_json()

        response = client.put(
            f"/tasks/{task_id}",
            json={},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        assert response.status_code == 200
        data = response.get_json()
        # Task should be unchanged
        assert data["title"] == original["title"]
        assert data["status"] == original["status"]


class TestAuthorizationHeader:
    def test_missing_authorization_header(self, client):
        """Test that missing Authorization header returns 401."""
        response = client.get("/tasks")
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_invalid_authorization_header_format(self, client):
        """Test that invalid Authorization header format returns 401."""
        response = client.get(
            "/tasks",
            headers={"Authorization": "InvalidFormat"}
        )
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_bearer_token_format(self, client, registered_user):
        """Test that Bearer token format is required."""
        response = client.get(
            "/tasks",
            headers={"Authorization": f"Bearer {registered_user['token']}"}
        )
        assert response.status_code == 200


class TestErrorHandling:
    def test_401_missing_token_message(self, client):
        """Test 401 error has proper message."""
        response = client.get("/tasks")
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_404_task_not_found_message(self, client, registered_user):
        """Test 404 error has proper message."""
        response = client.get(
            "/tasks/9999",
            headers={"Authorization": f"Bearer {registered_user['token']}"}
        )
        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "task not found"

    def test_responses_are_json(self, client, registered_user):
        """Test all responses are JSON."""
        # GET /tasks
        response = client.get(
            "/tasks",
            headers={"Authorization": f"Bearer {registered_user['token']}"}
        )
        assert response.content_type == "application/json"

        # POST /tasks
        response = client.post(
            "/tasks",
            json={"title": "Test"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        assert response.content_type == "application/json"

        # GET /tasks/{id}
        task_id = response.get_json()["id"]
        response = client.get(
            f"/tasks/{task_id}",
            headers={"Authorization": f"Bearer {registered_user['token']}"}
        )
        assert response.content_type == "application/json"

        # PUT /tasks/{id}
        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        assert response.content_type == "application/json"

        # 401 error
        response = client.get("/tasks")
        assert response.content_type == "application/json"

        # 404 error
        response = client.get(
            "/tasks/9999",
            headers={"Authorization": f"Bearer {registered_user['token']}"}
        )
        assert response.content_type == "application/json"


class TestEdgeCases:
    def test_task_id_uniqueness(self, client, registered_user):
        """Test that each task has a unique ID."""
        resp1 = client.post(
            "/tasks",
            json={"title": "Task 1"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        resp2 = client.post(
            "/tasks",
            json={"title": "Task 2"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )

        id1 = resp1.get_json()["id"]
        id2 = resp2.get_json()["id"]

        assert id1 != id2

    def test_update_preserves_created_at(self, client, registered_user):
        """Test that updating a task doesn't change created_at."""
        create_resp = client.post(
            "/tasks",
            json={"title": "Task"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        task_id = create_resp.get_json()["id"]
        original_created_at = create_resp.get_json()["created_at"]

        # Update the task
        client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )

        # Get the task and verify created_at is unchanged
        response = client.get(
            f"/tasks/{task_id}",
            headers={"Authorization": f"Bearer {registered_user['token']}"}
        )
        data = response.get_json()
        assert data["created_at"] == original_created_at

    def test_title_with_special_characters(self, client, registered_user):
        """Test creating a task with special characters in title."""
        special_title = "Task with \"quotes\", 'apostrophes', <tags>, & symbols"
        response = client.post(
            "/tasks",
            json={"title": special_title},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == special_title

    def test_multiple_tasks_lifecycle(self, client, registered_user):
        """Test creating, reading, and updating multiple tasks."""
        # Create 3 tasks
        ids = []
        for i in range(3):
            resp = client.post(
                "/tasks",
                json={"title": f"Task {i}"},
                headers={"Authorization": f"Bearer {registered_user['token']}"},
                content_type="application/json"
            )
            ids.append(resp.get_json()["id"])

        # Update first task
        client.put(
            f"/tasks/{ids[0]}",
            json={"status": "completed"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )

        # Update second task
        client.put(
            f"/tasks/{ids[1]}",
            json={"status": "in_progress"},
            headers={"Authorization": f"Bearer {registered_user['token']}"},
            content_type="application/json"
        )

        # List all tasks and verify
        response = client.get(
            "/tasks",
            headers={"Authorization": f"Bearer {registered_user['token']}"}
        )
        data = response.get_json()
        assert len(data) == 3

        statuses = {t["id"]: t["status"] for t in data}
        assert statuses[ids[0]] == "completed"
        assert statuses[ids[1]] == "in_progress"
        assert statuses[ids[2]] == "pending"

    def test_password_hashing(self, client, registered_user):
        """Test that passwords are hashed, not stored as plaintext."""
        # Connect to database and verify password is hashed
        import sqlite3
        import app as app_module
        conn = sqlite3.connect(app_module.DATABASE)
        conn.row_factory = sqlite3.Row

        row = conn.execute("SELECT password_hash FROM users WHERE username = ?", (registered_user["username"],)).fetchone()
        password_hash = row["password_hash"] if row else None
        conn.close()

        # Password should not be stored as plaintext
        assert password_hash is not None
        assert password_hash != registered_user["password"]
        # werkzeug hash format includes algorithm prefix and $ separators
        assert "$" in password_hash  # werkzeug hashes contain $ delimiters
