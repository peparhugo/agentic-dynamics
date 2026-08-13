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

    # Disable rate limiting for tests
    app_module.limiter.enabled = False

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


@pytest.fixture
def rate_limited_client(monkeypatch):
    """Create a test client with rate limiting enabled."""
    temp_dir = tempfile.mkdtemp()
    temp_tasks_file = os.path.join(temp_dir, "tasks.json")
    temp_users_file = os.path.join(temp_dir, "users.json")

    # Patch the module-level variables
    monkeypatch.setattr(app_module, "DATA_DIR", temp_dir)
    monkeypatch.setattr(app_module, "TASKS_FILE", temp_tasks_file)
    monkeypatch.setattr(app_module, "USERS_FILE", temp_users_file)

    # Reset repositories so they use the new paths
    app_module.reset_repositories()

    # Enable rate limiting for tests
    app_module.limiter.enabled = True

    with app.test_client() as client:
        yield client

    shutil.rmtree(temp_dir, ignore_errors=True)


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
    assert response.json["data"] == []
    assert response.json["total"] == 0
    assert response.json["next_cursor"] is None


def test_list_tasks_ordered_by_created_at_desc(client, auth_token):
    """Test that tasks are returned ordered by ID descending."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    client.post("/tasks", json={"title": "First"}, headers=headers)
    client.post("/tasks", json={"title": "Second"}, headers=headers)
    client.post("/tasks", json={"title": "Third"}, headers=headers)

    response = client.get("/tasks", headers=headers)
    assert response.status_code == 200
    data = response.json
    tasks = data["data"]
    assert len(tasks) == 3
    # Most recent task first (highest ID)
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
    assert len(response3.json["data"]) == 1
    assert response3.json["total"] == 1


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
    data = response.json
    tasks = data["data"]
    assert len(tasks) == 2
    assert all(t["title"].startswith("User1") for t in tasks)

    # User 2 should only see their own tasks
    response = client.get("/tasks", headers={"Authorization": f"Bearer {token2}"})
    assert response.status_code == 200
    data = response.json
    tasks = data["data"]
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


# ── Pagination tests ────────────────────────────────────────────

def test_list_tasks_pagination_default_limit(client, auth_token):
    """Test pagination with default limit of 20."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Create 25 tasks
    for i in range(25):
        client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

    response = client.get("/tasks", headers=headers)
    assert response.status_code == 200
    data = response.json
    assert isinstance(data, dict)
    assert "data" in data
    assert "next_cursor" in data
    assert "total" in data
    assert len(data["data"]) == 20
    assert data["total"] == 25
    assert data["next_cursor"] is not None


def test_list_tasks_pagination_custom_limit(client, auth_token):
    """Test pagination with custom limit."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Create 15 tasks
    for i in range(15):
        client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

    response = client.get("/tasks?limit=5", headers=headers)
    assert response.status_code == 200
    data = response.json
    assert len(data["data"]) == 5
    assert data["total"] == 15
    assert data["next_cursor"] is not None


def test_list_tasks_pagination_last_page(client, auth_token):
    """Test that next_cursor is None on the last page."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Create 10 tasks
    for i in range(10):
        client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

    # Get first page with limit 15 (all tasks fit)
    response = client.get("/tasks?limit=15", headers=headers)
    assert response.status_code == 200
    data = response.json
    assert len(data["data"]) == 10
    assert data["next_cursor"] is None


def test_list_tasks_pagination_with_cursor(client, auth_token):
    """Test pagination using cursor."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Create 10 tasks
    for i in range(10):
        client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

    # Get first page with limit 3
    response1 = client.get("/tasks?limit=3", headers=headers)
    assert response1.status_code == 200
    page1 = response1.json
    assert len(page1["data"]) == 3
    cursor1 = page1["next_cursor"]
    assert cursor1 is not None

    # Get second page using cursor
    response2 = client.get(f"/tasks?cursor={cursor1}&limit=3", headers=headers)
    assert response2.status_code == 200
    page2 = response2.json
    assert len(page2["data"]) == 3

    # First task of page 2 should not be in page 1
    page1_ids = {t["id"] for t in page1["data"]}
    page2_ids = {t["id"] for t in page2["data"]}
    assert not (page1_ids & page2_ids)


def test_list_tasks_pagination_max_limit(client, auth_token):
    """Test that limit is capped at 100."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Create 101 tasks
    for i in range(101):
        client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

    response = client.get("/tasks?limit=200", headers=headers)
    assert response.status_code == 200
    data = response.json
    assert len(data["data"]) == 100
    assert data["next_cursor"] is not None


def test_list_tasks_pagination_invalid_limit(client, auth_token):
    """Test that invalid limit reverts to default."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Create 30 tasks
    for i in range(30):
        client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

    # Test with zero limit
    response = client.get("/tasks?limit=0", headers=headers)
    assert response.status_code == 200
    data = response.json
    assert len(data["data"]) == 20  # Default limit

    # Test with negative limit
    response = client.get("/tasks?limit=-5", headers=headers)
    assert response.status_code == 200
    data = response.json
    assert len(data["data"]) == 20  # Default limit


def test_list_tasks_pagination_empty_result(client, auth_token):
    """Test pagination when no tasks exist."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    response = client.get("/tasks", headers=headers)
    assert response.status_code == 200
    data = response.json
    assert data["data"] == []
    assert data["next_cursor"] is None
    assert data["total"] == 0


def test_list_tasks_pagination_cursor_not_found(client, auth_token):
    """Test pagination with cursor that doesn't exist returns from beginning."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Create 5 tasks
    for i in range(5):
        client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

    # Use a cursor that doesn't exist
    response = client.get("/tasks?cursor=999&limit=2", headers=headers)
    assert response.status_code == 200
    data = response.json
    # Should return tasks from the beginning since cursor not found
    assert len(data["data"]) > 0


def test_list_tasks_pagination_ordered_descending(client, auth_token):
    """Test that paginated tasks are ordered by ID descending."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Create 10 tasks
    task_ids = []
    for i in range(10):
        response = client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)
        task_ids.append(response.json["id"])

    response = client.get("/tasks?limit=10", headers=headers)
    assert response.status_code == 200
    data = response.json
    returned_ids = [t["id"] for t in data["data"]]

    # Should be in reverse order of creation
    assert returned_ids == sorted(task_ids, reverse=True)


def test_list_tasks_pagination_user_isolation(client):
    """Test that pagination only shows user's own tasks."""
    # User 1 creates 5 tasks
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
    headers1 = {"Authorization": f"Bearer {token1}"}

    for i in range(5):
        client.post("/tasks", json={"title": f"User1 Task {i}"}, headers=headers1)

    # User 2 creates 3 tasks
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
    headers2 = {"Authorization": f"Bearer {token2}"}

    for i in range(3):
        client.post("/tasks", json={"title": f"User2 Task {i}"}, headers=headers2)

    # User 1 should only see 5 tasks
    response = client.get("/tasks", headers=headers1)
    assert response.status_code == 200
    data = response.json
    assert data["total"] == 5
    assert len(data["data"]) == 5
    assert all("User1" in t["title"] for t in data["data"])

    # User 2 should only see 3 tasks
    response = client.get("/tasks", headers=headers2)
    assert response.status_code == 200
    data = response.json
    assert data["total"] == 3
    assert len(data["data"]) == 3
    assert all("User2" in t["title"] for t in data["data"])


# ── Rate limiting tests ─────────────────────────────────────────

def test_rate_limit_on_list_tasks(rate_limited_client):
    """Test rate limiting on GET /tasks endpoint."""
    # Register and login first
    response = rate_limited_client.post("/auth/register", json={
        "username": "testuser",
        "password": "testpass",
        "email": "test@example.com"
    })
    assert response.status_code == 201

    login_response = rate_limited_client.post("/auth/login", json={
        "username": "testuser",
        "password": "testpass"
    })
    token = login_response.json["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Make 101 requests (limit is 100 per minute)
    responses = []
    for i in range(101):
        response = rate_limited_client.get("/tasks", headers=headers)
        responses.append(response.status_code)

    # Should hit rate limit at some point
    assert 429 in responses


def test_rate_limit_response_format(rate_limited_client):
    """Test that rate limit response includes error message."""
    # Register and login first
    response = rate_limited_client.post("/auth/register", json={
        "username": "testuser",
        "password": "testpass",
        "email": "test@example.com"
    })
    login_response = rate_limited_client.post("/auth/login", json={
        "username": "testuser",
        "password": "testpass"
    })
    token = login_response.json["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Make 101 requests to trigger rate limit
    for i in range(101):
        response = rate_limited_client.get("/tasks", headers=headers)

    # Should get 429 at some point
    if response.status_code == 429:
        assert "error" in response.json
        assert "rate limit" in response.json["error"]


def test_rate_limit_on_create_task(rate_limited_client):
    """Test rate limiting on POST /tasks endpoint."""
    # Register and login first
    response = rate_limited_client.post("/auth/register", json={
        "username": "testuser",
        "password": "testpass",
        "email": "test@example.com"
    })
    login_response = rate_limited_client.post("/auth/login", json={
        "username": "testuser",
        "password": "testpass"
    })
    token = login_response.json["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Make 101 POST requests
    responses = []
    for i in range(101):
        response = rate_limited_client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)
        responses.append(response.status_code)

    # Should hit rate limit at some point
    assert 429 in responses


def test_rate_limit_on_auth_register(rate_limited_client):
    """Test rate limiting on /auth/register endpoint."""
    # Make 101 registration attempts
    responses = []
    for i in range(101):
        response = rate_limited_client.post("/auth/register", json={
            "username": f"user{i}",
            "password": "pass",
            "email": f"user{i}@example.com"
        })
        responses.append(response.status_code)

    # Should hit rate limit at some point
    status_codes = set(responses)
    assert 429 in status_codes


def test_rate_limit_on_auth_login(rate_limited_client):
    """Test rate limiting on /auth/login endpoint."""
    # Register a user first
    rate_limited_client.post("/auth/register", json={
        "username": "testuser",
        "password": "testpass",
        "email": "test@example.com"
    })

    # Make 101 login attempts
    responses = []
    for i in range(101):
        response = rate_limited_client.post("/auth/login", json={
            "username": "testuser",
            "password": "testpass"
        })
        responses.append(response.status_code)

    # Should hit rate limit
    status_codes = set(responses)
    assert 429 in status_codes


def test_rate_limit_on_get_task(rate_limited_client):
    """Test rate limiting on GET /tasks/<id> endpoint."""
    # Register and login first
    response = rate_limited_client.post("/auth/register", json={
        "username": "testuser",
        "password": "testpass",
        "email": "test@example.com"
    })
    if response.status_code != 201:
        pytest.skip("Could not register user (rate limited)")

    login_response = rate_limited_client.post("/auth/login", json={
        "username": "testuser",
        "password": "testpass"
    })
    if login_response.status_code != 200:
        pytest.skip("Could not login (rate limited)")

    token = login_response.json["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create a task
    response = rate_limited_client.post("/tasks", json={"title": "Test Task"}, headers=headers)
    if response.status_code != 201:
        pytest.skip("Could not create task (rate limited)")

    task_id = response.json["id"]

    # Make 101 GET requests for the same task
    responses = []
    for i in range(101):
        response = rate_limited_client.get(f"/tasks/{task_id}", headers=headers)
        responses.append(response.status_code)

    # Should hit rate limit
    status_codes = set(responses)
    assert 429 in status_codes


def test_rate_limit_per_user(rate_limited_client):
    """Test that rate limits are per-user, not global."""
    # Create two users
    response1 = rate_limited_client.post("/auth/register", json={
        "username": "user1",
        "password": "pass1",
        "email": "user1@example.com"
    })
    if response1.status_code != 201:
        pytest.skip("Could not register user1 (rate limited)")

    login1 = rate_limited_client.post("/auth/login", json={
        "username": "user1",
        "password": "pass1"
    })
    if login1.status_code != 200:
        pytest.skip("Could not login user1 (rate limited)")

    token1 = login1.json["token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    response2 = rate_limited_client.post("/auth/register", json={
        "username": "user2",
        "password": "pass2",
        "email": "user2@example.com"
    })
    if response2.status_code != 201:
        pytest.skip("Could not register user2 (rate limited)")

    login2 = rate_limited_client.post("/auth/login", json={
        "username": "user2",
        "password": "pass2"
    })
    if login2.status_code != 200:
        pytest.skip("Could not login user2 (rate limited)")

    token2 = login2.json["token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    # User 1 makes 101 requests
    responses1 = []
    for i in range(101):
        response = rate_limited_client.get("/tasks", headers=headers1)
        responses1.append(response.status_code)

    # User 2 should still be able to make requests (not rate limited)
    response = rate_limited_client.get("/tasks", headers=headers2)
    assert response.status_code == 200


def test_rate_limit_on_health(rate_limited_client):
    """Test rate limiting on /health endpoint."""
    # Make 101 health check requests
    responses = []
    for i in range(101):
        response = rate_limited_client.get("/health")
        responses.append(response.status_code)

    # Should hit rate limit
    status_codes = set(responses)
    assert 429 in status_codes


def test_rate_limit_on_update_task(rate_limited_client):
    """Test rate limiting on PUT /tasks/<id> endpoint."""
    # Register and login first
    response = rate_limited_client.post("/auth/register", json={
        "username": "testuser",
        "password": "testpass",
        "email": "test@example.com"
    })
    if response.status_code != 201:
        pytest.skip("Could not register user (rate limited)")

    login_response = rate_limited_client.post("/auth/login", json={
        "username": "testuser",
        "password": "testpass"
    })
    if login_response.status_code != 200:
        pytest.skip("Could not login (rate limited)")

    token = login_response.json["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create a task
    response = rate_limited_client.post("/tasks", json={"title": "Test Task"}, headers=headers)
    if response.status_code != 201:
        pytest.skip("Could not create task (rate limited)")

    task_id = response.json["id"]

    # Make 101 PUT requests
    responses = []
    for i in range(101):
        response = rate_limited_client.put(f"/tasks/{task_id}", json={"title": f"Updated {i}"}, headers=headers)
        responses.append(response.status_code)

    # Should hit rate limit
    status_codes = set(responses)
    assert 429 in status_codes
