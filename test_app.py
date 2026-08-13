"""
pytest tests for the task management API.
"""

import pytest
import json
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from app import app
import app as app_module


@pytest.fixture
def client(monkeypatch):
    """Create a test client with a temporary data directory."""
    temp_dir = tempfile.mkdtemp()
    temp_tasks_file = os.path.join(temp_dir, "tasks.json")
    temp_users_file = os.path.join(temp_dir, "users.json")

    # Patch the module-level variables
    monkeypatch.setattr(app_module, "DATA_DIR", temp_dir)
    monkeypatch.setattr(app_module, "TASKS_FILE", temp_tasks_file)
    monkeypatch.setattr(app_module, "USERS_FILE", temp_users_file)

    # Reset repositories so they use the new paths
    app_module.reset_repositories()

    with app.test_client() as client:
        yield client

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def auth_token(client):
    """Register a user and return their auth token."""
    response = client.post("/auth/register", json={
        "username": "testuser",
        "password": "testpass123",
        "email": "testuser@example.com"
    })
    assert response.status_code == 201

    login_response = client.post("/auth/login", json={
        "username": "testuser",
        "password": "testpass123"
    })
    assert login_response.status_code == 200
    return login_response.json["token"]


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"


# ── Auth tests ──────────────────────────────────────────────────

def test_register_success(client):
    """Test registering a new user."""
    response = client.post("/auth/register", json={
        "username": "newuser",
        "password": "password123",
        "email": "newuser@example.com"
    })
    assert response.status_code == 201
    assert response.json["username"] == "newuser"
    assert response.json["email"] == "newuser@example.com"
    assert "id" in response.json


def test_register_duplicate_username(client):
    """Test registering with an existing username returns 409."""
    client.post("/auth/register", json={
        "username": "user1",
        "password": "pass1",
        "email": "user1@example.com"
    })
    response = client.post("/auth/register", json={
        "username": "user1",
        "password": "pass2",
        "email": "user1b@example.com"
    })
    assert response.status_code == 409
    assert "already exists" in response.json["error"]


def test_register_missing_username(client):
    """Test registering without username returns 400."""
    response = client.post("/auth/register", json={
        "password": "password123",
        "email": "user@example.com"
    })
    assert response.status_code == 400
    assert "required" in response.json["error"]


def test_register_missing_password(client):
    """Test registering without password returns 400."""
    response = client.post("/auth/register", json={
        "username": "user1",
        "email": "user@example.com"
    })
    assert response.status_code == 400
    assert "required" in response.json["error"]


def test_register_missing_email(client):
    """Test registering without email returns 400."""
    response = client.post("/auth/register", json={
        "username": "user1",
        "password": "password123"
    })
    assert response.status_code == 400
    assert "required" in response.json["error"]


def test_login_success(client):
    """Test logging in with valid credentials."""
    client.post("/auth/register", json={
        "username": "testuser",
        "password": "testpass",
        "email": "testuser@example.com"
    })
    response = client.post("/auth/login", json={
        "username": "testuser",
        "password": "testpass"
    })
    assert response.status_code == 200
    assert "token" in response.json


def test_login_invalid_password(client):
    """Test login with wrong password returns 401."""
    client.post("/auth/register", json={
        "username": "testuser",
        "password": "correctpass",
        "email": "testuser@example.com"
    })
    response = client.post("/auth/login", json={
        "username": "testuser",
        "password": "wrongpass"
    })
    assert response.status_code == 401
    assert "invalid" in response.json["error"]


def test_login_nonexistent_user(client):
    """Test login with non-existent user returns 401."""
    response = client.post("/auth/login", json={
        "username": "nouser",
        "password": "anypass"
    })
    assert response.status_code == 401
    assert "invalid" in response.json["error"]


def test_login_missing_credentials(client):
    """Test login without credentials returns 400."""
    response = client.post("/auth/login", json={})
    assert response.status_code == 400
    assert "required" in response.json["error"]


# ── Task tests with auth ────────────────────────────────────────

def test_create_task_success(client, auth_token):
    """Test creating a task with valid data and auth token."""
    response = client.post("/tasks", json={"title": "Test Task"}, headers={
        "Authorization": f"Bearer {auth_token}"
    })
    assert response.status_code == 201
    data = response.json
    assert data["id"] == 1
    assert data["title"] == "Test Task"
    assert data["status"] == "pending"
    assert data["owner_id"] is not None
    assert "created_at" in data


def test_create_task_missing_title(client, auth_token):
    """Test creating a task without a title returns 400."""
    response = client.post("/tasks", json={}, headers={
        "Authorization": f"Bearer {auth_token}"
    })
    assert response.status_code == 400
    assert "error" in response.json
    assert "title" in response.json["error"]


def test_create_task_empty_title(client, auth_token):
    """Test creating a task with empty title returns 400."""
    response = client.post("/tasks", json={"title": ""}, headers={
        "Authorization": f"Bearer {auth_token}"
    })
    assert response.status_code == 400
    assert "error" in response.json


def test_create_task_whitespace_title(client, auth_token):
    """Test creating a task with whitespace-only title returns 400."""
    response = client.post("/tasks", json={"title": "   "}, headers={
        "Authorization": f"Bearer {auth_token}"
    })
    assert response.status_code == 400
    assert "error" in response.json


def test_create_task_no_json(client, auth_token):
    """Test creating a task without JSON body returns 400."""
    response = client.post("/tasks", json={"other": "field"}, headers={
        "Authorization": f"Bearer {auth_token}"
    })
    assert response.status_code == 400


def test_create_task_missing_auth(client):
    """Test creating a task without auth returns 401."""
    response = client.post("/tasks", json={"title": "Test"})
    assert response.status_code == 401
    assert "authorization" in response.json["error"]


def test_create_task_invalid_token(client):
    """Test creating a task with invalid token returns 401."""
    response = client.post("/tasks", json={"title": "Test"}, headers={
        "Authorization": "Bearer invalid.token.here"
    })
    assert response.status_code == 401
    assert "invalid" in response.json["error"] or "expired" in response.json["error"]


def test_create_multiple_tasks(client, auth_token):
    """Test creating multiple tasks with incrementing IDs."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response1 = client.post("/tasks", json={"title": "First Task"}, headers=headers)
    response2 = client.post("/tasks", json={"title": "Second Task"}, headers=headers)

    assert response1.status_code == 201
    assert response2.status_code == 201
    assert response1.json["id"] == 1
    assert response2.json["id"] == 2


def test_list_tasks_empty(client, auth_token):
    """Test listing tasks when none exist."""
    response = client.get("/tasks", headers={
        "Authorization": f"Bearer {auth_token}"
    })
    assert response.status_code == 200
    assert response.json == []


def test_list_tasks_ordered_by_created_at_desc(client, auth_token):
    """Test that tasks are returned ordered by created_at descending."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    client.post("/tasks", json={"title": "First"}, headers=headers)
    client.post("/tasks", json={"title": "Second"}, headers=headers)
    client.post("/tasks", json={"title": "Third"}, headers=headers)

    response = client.get("/tasks", headers=headers)
    assert response.status_code == 200
    tasks = response.json
    assert len(tasks) == 3
    # Most recent task first
    assert tasks[0]["title"] == "Third"
    assert tasks[1]["title"] == "Second"
    assert tasks[2]["title"] == "First"


def test_get_task_success(client, auth_token):
    """Test getting a single task by ID."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    create_response = client.post("/tasks", json={"title": "Test Task"}, headers=headers)
    task_id = create_response.json["id"]

    response = client.get(f"/tasks/{task_id}", headers=headers)
    assert response.status_code == 200
    assert response.json["id"] == task_id
    assert response.json["title"] == "Test Task"


def test_get_task_not_found(client, auth_token):
    """Test getting a non-existent task returns 404."""
    response = client.get("/tasks/999", headers={
        "Authorization": f"Bearer {auth_token}"
    })
    assert response.status_code == 404
    assert "error" in response.json
    assert "not found" in response.json["error"]


def test_get_task_missing_auth(client):
    """Test getting a task without auth returns 401."""
    response = client.get("/tasks/1")
    assert response.status_code == 401


def test_get_task_unauthorized(client):
    """Test that users can only access their own tasks."""
    headers1 = {"Authorization": "Bearer token1"}
    headers2 = {"Authorization": "Bearer token2"}

    # Register and create task as user 1
    response1 = client.post("/auth/register", json={
        "username": "user1",
        "password": "pass1",
        "email": "user1@example.com"
    })
    user1_id = response1.json["id"]

    login1 = client.post("/auth/login", json={
        "username": "user1",
        "password": "pass1"
    })
    token1 = login1.json["token"]

    create_response = client.post("/tasks", json={"title": "User1 Task"}, headers={
        "Authorization": f"Bearer {token1}"
    })
    task_id = create_response.json["id"]

    # Register user 2
    response2 = client.post("/auth/register", json={
        "username": "user2",
        "password": "pass2",
        "email": "user2@example.com"
    })
    login2 = client.post("/auth/login", json={
        "username": "user2",
        "password": "pass2"
    })
    token2 = login2.json["token"]

    # User 2 should not be able to access user 1's task
    response = client.get(f"/tasks/{task_id}", headers={
        "Authorization": f"Bearer {token2}"
    })
    assert response.status_code == 403
    assert "unauthorized" in response.json["error"]


def test_update_task_title(client, auth_token):
    """Test updating a task's title."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    create_response = client.post("/tasks", json={"title": "Original"}, headers=headers)
    task_id = create_response.json["id"]

    response = client.put(f"/tasks/{task_id}", json={"title": "Updated"}, headers=headers)
    assert response.status_code == 200
    assert response.json["title"] == "Updated"
    assert response.json["status"] == "pending"


def test_update_task_status(client, auth_token):
    """Test updating a task's status."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    create_response = client.post("/tasks", json={"title": "Test"}, headers=headers)
    task_id = create_response.json["id"]

    response = client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)
    assert response.status_code == 200
    assert response.json["status"] == "completed"
    assert response.json["title"] == "Test"


def test_update_task_both_fields(client, auth_token):
    """Test updating both title and status."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    create_response = client.post("/tasks", json={"title": "Original"}, headers=headers)
    task_id = create_response.json["id"]

    response = client.put(f"/tasks/{task_id}", json={
        "title": "New Title",
        "status": "in_progress"
    }, headers=headers)
    assert response.status_code == 200
    assert response.json["title"] == "New Title"
    assert response.json["status"] == "in_progress"


def test_update_task_empty_title(client, auth_token):
    """Test updating with empty title returns 400."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    create_response = client.post("/tasks", json={"title": "Original"}, headers=headers)
    task_id = create_response.json["id"]

    response = client.put(f"/tasks/{task_id}", json={"title": ""}, headers=headers)
    assert response.status_code == 400
    assert "error" in response.json


def test_update_task_not_found(client, auth_token):
    """Test updating a non-existent task returns 404."""
    response = client.put("/tasks/999", json={"title": "New"}, headers={
        "Authorization": f"Bearer {auth_token}"
    })
    assert response.status_code == 404
    assert "error" in response.json


def test_update_task_missing_auth(client):
    """Test updating a task without auth returns 401."""
    response = client.put("/tasks/1", json={"title": "New"})
    assert response.status_code == 401


def test_update_task_unauthorized(client):
    """Test that users can only update their own tasks."""
    # Register and create task as user 1
    response1 = client.post("/auth/register", json={
        "username": "user1",
        "password": "pass1",
        "email": "user1@example.com"
    })

    login1 = client.post("/auth/login", json={
        "username": "user1",
        "password": "pass1"
    })
    token1 = login1.json["token"]

    create_response = client.post("/tasks", json={"title": "User1 Task"}, headers={
        "Authorization": f"Bearer {token1}"
    })
    task_id = create_response.json["id"]

    # Register user 2
    client.post("/auth/register", json={
        "username": "user2",
        "password": "pass2",
        "email": "user2@example.com"
    })
    login2 = client.post("/auth/login", json={
        "username": "user2",
        "password": "pass2"
    })
    token2 = login2.json["token"]

    # User 2 should not be able to update user 1's task
    response = client.put(f"/tasks/{task_id}", json={"title": "Hacked"}, headers={
        "Authorization": f"Bearer {token2}"
    })
    assert response.status_code == 403
    assert "unauthorized" in response.json["error"]


def test_update_task_no_changes(client, auth_token):
    """Test updating a task with no fields just returns the task."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    create_response = client.post("/tasks", json={"title": "Test"}, headers=headers)
    task_id = create_response.json["id"]
    original_title = create_response.json["title"]

    response = client.put(f"/tasks/{task_id}", json={}, headers=headers)
    assert response.status_code == 200
    assert response.json["title"] == original_title


def test_persistence_across_requests(client, auth_token):
    """Test that data persists across multiple requests."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response1 = client.post("/tasks", json={"title": "Persistent Task"}, headers=headers)
    task_id = response1.json["id"]

    response2 = client.get(f"/tasks/{task_id}", headers=headers)
    assert response2.status_code == 200
    assert response2.json["title"] == "Persistent Task"

    response3 = client.get("/tasks", headers=headers)
    assert len(response3.json) == 1


def test_task_created_at_format(client, auth_token):
    """Test that created_at is in ISO format."""
    response = client.post("/tasks", json={"title": "Test"}, headers={
        "Authorization": f"Bearer {auth_token}"
    })
    created_at = response.json["created_at"]
    # ISO format includes 'T' and microseconds or 'Z'
    assert "T" in created_at or "Z" in created_at


def test_create_task_with_extra_fields(client, auth_token):
    """Test that extra fields in request are ignored."""
    response = client.post("/tasks", json={
        "title": "Test",
        "extra_field": "ignored",
        "another": "also ignored"
    }, headers={"Authorization": f"Bearer {auth_token}"})
    assert response.status_code == 201
    # Response should only have expected fields
    assert "extra_field" not in response.json
    assert "another" not in response.json


def test_user_isolation_list_tasks(client):
    """Test that users only see their own tasks in list."""
    # User 1 creates tasks
    response1 = client.post("/auth/register", json={
        "username": "user1",
        "password": "pass1",
        "email": "user1@example.com"
    })
    login1 = client.post("/auth/login", json={
        "username": "user1",
        "password": "pass1"
    })
    token1 = login1.json["token"]

    client.post("/tasks", json={"title": "User1 Task1"}, headers={
        "Authorization": f"Bearer {token1}"
    })
    client.post("/tasks", json={"title": "User1 Task2"}, headers={
        "Authorization": f"Bearer {token1}"
    })

    # User 2 creates tasks
    client.post("/auth/register", json={
        "username": "user2",
        "password": "pass2",
        "email": "user2@example.com"
    })
    login2 = client.post("/auth/login", json={
        "username": "user2",
        "password": "pass2"
    })
    token2 = login2.json["token"]

    client.post("/tasks", json={"title": "User2 Task1"}, headers={
        "Authorization": f"Bearer {token2}"
    })

    # User 1 should only see their own tasks
    response = client.get("/tasks", headers={"Authorization": f"Bearer {token1}"})
    assert response.status_code == 200
    tasks = response.json
    assert len(tasks) == 2
    assert all(t["title"].startswith("User1") for t in tasks)

    # User 2 should only see their own tasks
    response = client.get("/tasks", headers={"Authorization": f"Bearer {token2}"})
    assert response.status_code == 200
    tasks = response.json
    assert len(tasks) == 1
    assert tasks[0]["title"] == "User2 Task1"


# ── Notification tests ──────────────────────────────────────────

def test_notification_sent_when_status_changes_to_completed(client, auth_token):
    """Test that a notification email is triggered when status changes to 'completed'."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    create_response = client.post("/tasks", json={"title": "Test Task"}, headers=headers)
    task_id = create_response.json["id"]

    with patch("app.send_notification_email.delay") as mock_delay:
        response = client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)
        assert response.status_code == 200
        assert response.json["status"] == "completed"
        mock_delay.assert_called_once()
        args = mock_delay.call_args
        assert args[0][0] == "testuser@example.com"
        assert args[0][1] == "Test Task"


def test_notification_not_sent_on_other_status_changes(client, auth_token):
    """Test that notification is not sent when changing to non-completed status."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    create_response = client.post("/tasks", json={"title": "Test Task"}, headers=headers)
    task_id = create_response.json["id"]

    with patch("app.send_notification_email.delay") as mock_delay:
        response = client.put(f"/tasks/{task_id}", json={"status": "in_progress"}, headers=headers)
        assert response.status_code == 200
        assert response.json["status"] == "in_progress"
        mock_delay.assert_not_called()


def test_notification_not_resent_if_already_completed(client, auth_token):
    """Test that notification is not resent if task is already completed and status doesn't change."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    create_response = client.post("/tasks", json={"title": "Test Task"}, headers=headers)
    task_id = create_response.json["id"]

    with patch("app.send_notification_email.delay") as mock_delay:
        client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)
        assert mock_delay.call_count == 1

        client.put(f"/tasks/{task_id}", json={"title": "Updated Title"}, headers=headers)
        assert mock_delay.call_count == 1

        client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)
        assert mock_delay.call_count == 1


def test_notification_includes_correct_user_email(client):
    """Test that notification includes the correct user's email."""
    response1 = client.post("/auth/register", json={
        "username": "user1",
        "password": "pass1",
        "email": "user1@test.com"
    })

    login1 = client.post("/auth/login", json={
        "username": "user1",
        "password": "pass1"
    })
    token1 = login1.json["token"]

    headers = {"Authorization": f"Bearer {token1}"}
    create_response = client.post("/tasks", json={"title": "Important Task"}, headers=headers)
    task_id = create_response.json["id"]

    with patch("app.send_notification_email.delay") as mock_delay:
        response = client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=headers)
        assert response.status_code == 200
        mock_delay.assert_called_once()
        args = mock_delay.call_args
        assert args[0][0] == "user1@test.com"
        assert args[0][1] == "Important Task"


def test_notification_not_sent_when_status_not_in_request(client, auth_token):
    """Test that notification is not sent if status is not in the request."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    create_response = client.post("/tasks", json={"title": "Test Task"}, headers=headers)
    task_id = create_response.json["id"]

    with patch("app.send_notification_email.delay") as mock_delay:
        response = client.put(f"/tasks/{task_id}", json={"title": "New Title"}, headers=headers)
        assert response.status_code == 200
        mock_delay.assert_not_called()
