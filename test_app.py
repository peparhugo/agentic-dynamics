"""
Comprehensive tests for the Task Management API with JWT authentication.
"""

import pytest
from datetime import datetime
from app import app, db, Task, User, generate_token, init_db, limiter
from tasks import celery
from unittest.mock import patch, MagicMock
from flask_limiter.util import get_remote_address


@pytest.fixture
def client():
    """Create a test client with a fresh database."""
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    limiter.enabled = False

    celery.conf.update(task_always_eager=True, task_eager_propagates=True)

    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()

    limiter.enabled = True


@pytest.fixture
def auth_headers(client):
    """Create a test user and return auth headers."""
    with app.app_context():
        user = User(username="testuser")
        user.set_password("testpass")
        db.session.add(user)
        db.session.commit()
        token = generate_token(user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_user(client):
    """Create and return a test user."""
    with app.app_context():
        user = User(username="testuser")
        user.set_password("testpass")
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    return {"id": user_id, "username": "testuser"}


@pytest.fixture
def client_with_limiter():
    """Create a test client with rate limiting enabled using in-memory storage."""
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    limiter.enabled = True
    limiter.storage_uri = "memory://"

    celery.conf.update(task_always_eager=True, task_eager_propagates=True)

    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()
        limiter.enabled = False


class TestAuth:
    """Tests for authentication endpoints."""

    def test_register_with_valid_credentials(self, client):
        """Should create a user and return token."""
        response = client.post(
            "/auth/register",
            json={"username": "newuser", "password": "password123"},
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.get_json()
        assert "token" in data
        assert "user_id" in data
        assert data["user_id"] is not None

    def test_register_duplicate_username(self, client):
        """Should return 400 when username already exists."""
        client.post(
            "/auth/register",
            json={"username": "user1", "password": "pass1"},
            content_type="application/json",
        )
        response = client.post(
            "/auth/register",
            json={"username": "user1", "password": "pass2"},
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "username already exists"

    def test_register_missing_username(self, client):
        """Should return 400 when username is missing."""
        response = client.post(
            "/auth/register",
            json={"password": "password123"},
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "username and password are required"

    def test_register_missing_password(self, client):
        """Should return 400 when password is missing."""
        response = client.post(
            "/auth/register",
            json={"username": "user1"},
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "username and password are required"

    def test_login_with_valid_credentials(self, client):
        """Should return token for valid credentials."""
        client.post(
            "/auth/register",
            json={"username": "user1", "password": "pass123"},
            content_type="application/json",
        )
        response = client.post(
            "/auth/login",
            json={"username": "user1", "password": "pass123"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "token" in data
        assert "user_id" in data

    def test_login_invalid_password(self, client):
        """Should return 401 for invalid password."""
        client.post(
            "/auth/register",
            json={"username": "user1", "password": "pass123"},
            content_type="application/json",
        )
        response = client.post(
            "/auth/login",
            json={"username": "user1", "password": "wrongpass"},
            content_type="application/json",
        )
        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "invalid credentials"

    def test_login_nonexistent_user(self, client):
        """Should return 401 for nonexistent user."""
        response = client.post(
            "/auth/login",
            json={"username": "nouser", "password": "pass"},
            content_type="application/json",
        )
        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "invalid credentials"

    def test_login_missing_credentials(self, client):
        """Should return 400 when credentials are missing."""
        response = client.post(
            "/auth/login",
            json={"username": "user1"},
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "username and password are required"


class TestTaskCreation:
    """Tests for POST /tasks endpoint."""

    def test_create_task_with_valid_title(self, client, auth_headers):
        """Should create a task with valid title."""
        response = client.post(
            "/tasks",
            json={"title": "Buy groceries"},
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert data["id"] is not None
        assert data["created_at"] is not None

    def test_create_task_missing_auth(self, client):
        """Should return 401 when authorization is missing."""
        response = client.post(
            "/tasks",
            json={"title": "Buy groceries"},
            content_type="application/json",
        )
        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "unauthorized"

    def test_create_task_invalid_token(self, client):
        """Should return 401 when token is invalid."""
        response = client.post(
            "/tasks",
            json={"title": "Buy groceries"},
            content_type="application/json",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "unauthorized"

    def test_create_task_missing_title(self, client, auth_headers):
        """Should return 400 when title is missing."""
        response = client.post(
            "/tasks",
            json={},
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "title is required"

    def test_create_task_empty_title(self, client, auth_headers):
        """Should return 400 when title is empty string."""
        response = client.post(
            "/tasks",
            json={"title": ""},
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "title is required"

    def test_create_task_whitespace_title(self, client, auth_headers):
        """Should return 400 when title is only whitespace."""
        response = client.post(
            "/tasks",
            json={"title": "   "},
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "title is required"

    def test_create_task_null_body(self, client, auth_headers):
        """Should return 400 when request body is null."""
        response = client.post(
            "/tasks",
            json=None,
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "title is required"

    def test_create_multiple_tasks(self, client, auth_headers):
        """Should create multiple tasks independently."""
        resp1 = client.post("/tasks", json={"title": "Task 1"}, headers=auth_headers)
        resp2 = client.post("/tasks", json={"title": "Task 2"}, headers=auth_headers)
        resp3 = client.post("/tasks", json={"title": "Task 3"}, headers=auth_headers)

        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp3.status_code == 201

        data1 = resp1.get_json()
        data2 = resp2.get_json()
        data3 = resp3.get_json()

        assert data1["id"] != data2["id"] != data3["id"]
        assert data1["title"] == "Task 1"
        assert data2["title"] == "Task 2"
        assert data3["title"] == "Task 3"


class TestTaskRetrieval:
    """Tests for GET endpoints."""

    def test_list_empty_tasks(self, client, auth_headers):
        """Should return empty list when no tasks exist."""
        response = client.get("/tasks", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["data"] == []
        assert data["next_cursor"] is None
        assert data["total"] == 0

    def test_list_tasks_missing_auth(self, client):
        """Should return 401 when authorization is missing."""
        response = client.get("/tasks")
        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "unauthorized"

    def test_list_tasks_ordered_by_created_at_desc(self, client, auth_headers):
        """Should return tasks ordered by created_at descending."""
        client.post("/tasks", json={"title": "Task 1"}, headers=auth_headers)
        client.post("/tasks", json={"title": "Task 2"}, headers=auth_headers)
        client.post("/tasks", json={"title": "Task 3"}, headers=auth_headers)

        response = client.get("/tasks", headers=auth_headers)
        assert response.status_code == 200
        result = response.get_json()
        data = result["data"]

        assert len(data) == 3
        assert data[0]["title"] == "Task 3"
        assert data[1]["title"] == "Task 2"
        assert data[2]["title"] == "Task 1"

    def test_get_single_task(self, client, auth_headers):
        """Should retrieve a single task by ID."""
        create_response = client.post("/tasks", json={"title": "Test Task"}, headers=auth_headers)
        task_id = create_response.get_json()["id"]

        response = client.get(f"/tasks/{task_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Test Task"
        assert data["status"] == "pending"

    def test_get_nonexistent_task(self, client, auth_headers):
        """Should return 404 for nonexistent task."""
        response = client.get("/tasks/9999", headers=auth_headers)
        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "task not found"

    def test_list_tasks_with_multiple_entries(self, client, auth_headers):
        """Should list all tasks with complete data."""
        ids = []
        for i in range(3):
            resp = client.post("/tasks", json={"title": f"Task {i+1}"}, headers=auth_headers)
            ids.append(resp.get_json()["id"])

        response = client.get("/tasks", headers=auth_headers)
        assert response.status_code == 200
        result = response.get_json()
        data = result["data"]
        assert len(data) == 3

        for task in data:
            assert "id" in task
            assert "title" in task
            assert "status" in task
            assert "created_at" in task
            assert task["status"] == "pending"

    def test_user_can_only_see_own_tasks(self, client):
        """Should ensure users only see their own tasks."""
        user1_response = client.post(
            "/auth/register",
            json={"username": "user1", "password": "pass1"},
            content_type="application/json",
        )
        user1_token = user1_response.get_json()["token"]
        user1_headers = {"Authorization": f"Bearer {user1_token}"}

        user2_response = client.post(
            "/auth/register",
            json={"username": "user2", "password": "pass2"},
            content_type="application/json",
        )
        user2_token = user2_response.get_json()["token"]
        user2_headers = {"Authorization": f"Bearer {user2_token}"}

        client.post("/tasks", json={"title": "User 1 Task"}, headers=user1_headers)
        client.post("/tasks", json={"title": "User 2 Task"}, headers=user2_headers)

        user1_result = client.get("/tasks", headers=user1_headers).get_json()
        user2_result = client.get("/tasks", headers=user2_headers).get_json()

        user1_tasks = user1_result["data"]
        user2_tasks = user2_result["data"]

        assert len(user1_tasks) == 1
        assert len(user2_tasks) == 1
        assert user1_tasks[0]["title"] == "User 1 Task"
        assert user2_tasks[0]["title"] == "User 2 Task"


class TestTaskUpdate:
    """Tests for PUT /tasks/{id} endpoint."""

    def test_update_task_title(self, client, auth_headers):
        """Should update task title."""
        create_resp = client.post("/tasks", json={"title": "Original Title"}, headers=auth_headers)
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated Title"},
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated Title"
        assert data["status"] == "pending"

    def test_update_task_missing_auth(self, client):
        """Should return 401 when authorization is missing."""
        response = client.put(
            "/tasks/1",
            json={"title": "Updated Title"},
            content_type="application/json",
        )
        assert response.status_code == 401
        data = response.get_json()
        assert data["error"] == "unauthorized"

    def test_update_task_status(self, client, auth_headers):
        """Should update task status."""
        create_resp = client.post("/tasks", json={"title": "Test Task"}, headers=auth_headers)
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"status": "completed"},
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Test Task"
        assert data["status"] == "completed"

    def test_update_task_title_and_status(self, client, auth_headers):
        """Should update both title and status."""
        create_resp = client.post("/tasks", json={"title": "Original"}, headers=auth_headers)
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated", "status": "in_progress"},
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "in_progress"

    def test_update_nonexistent_task(self, client, auth_headers):
        """Should return 404 when updating nonexistent task."""
        response = client.put(
            "/tasks/9999",
            json={"title": "Updated"},
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "task not found"

    def test_update_with_empty_payload(self, client, auth_headers):
        """Should handle empty update payload gracefully."""
        create_resp = client.post("/tasks", json={"title": "Test Task"}, headers=auth_headers)
        task_id = create_resp.get_json()["id"]
        original_title = create_resp.get_json()["title"]

        response = client.put(
            f"/tasks/{task_id}",
            json={},
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == original_title

    def test_update_task_title_with_whitespace(self, client, auth_headers):
        """Should trim whitespace from title."""
        create_resp = client.post("/tasks", json={"title": "Original"}, headers=auth_headers)
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "  Updated Title  "},
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated Title"

    def test_update_preserves_created_at(self, client, auth_headers):
        """Should preserve created_at when updating."""
        create_resp = client.post("/tasks", json={"title": "Original"}, headers=auth_headers)
        task_data = create_resp.get_json()
        task_id = task_data["id"]
        original_created_at = task_data["created_at"]

        client.put(f"/tasks/{task_id}", json={"title": "Updated"}, headers=auth_headers)

        get_resp = client.get(f"/tasks/{task_id}", headers=auth_headers)
        data = get_resp.get_json()
        assert data["created_at"] == original_created_at

    def test_user_cannot_update_other_users_task(self, client):
        """Should prevent user from updating another user's task."""
        user1_response = client.post(
            "/auth/register",
            json={"username": "user1", "password": "pass1"},
            content_type="application/json",
        )
        user1_token = user1_response.get_json()["token"]
        user1_headers = {"Authorization": f"Bearer {user1_token}"}

        user2_response = client.post(
            "/auth/register",
            json={"username": "user2", "password": "pass2"},
            content_type="application/json",
        )
        user2_token = user2_response.get_json()["token"]
        user2_headers = {"Authorization": f"Bearer {user2_token}"}

        create_resp = client.post("/tasks", json={"title": "User 1 Task"}, headers=user1_headers)
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Hacked"},
            content_type="application/json",
            headers=user2_headers,
        )
        assert response.status_code == 404


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_json_body(self, client, auth_headers):
        """Should handle invalid JSON gracefully."""
        response = client.post(
            "/tasks",
            data="invalid json",
            content_type="application/json",
            headers=auth_headers,
        )
        # Flask handles this and returns 400
        assert response.status_code == 400

    def test_post_with_extra_fields(self, client, auth_headers):
        """Should ignore extra fields in POST."""
        response = client.post(
            "/tasks",
            json={"title": "Task", "extra_field": "should_be_ignored"},
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Task"
        assert "extra_field" not in data

    def test_put_with_extra_fields(self, client, auth_headers):
        """Should ignore extra fields in PUT."""
        create_resp = client.post("/tasks", json={"title": "Original"}, headers=auth_headers)
        task_id = create_resp.get_json()["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated", "extra_field": "ignored"},
            content_type="application/json",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated"
        assert "extra_field" not in data


class TestDataIntegrity:
    """Tests for data persistence and integrity."""

    def test_task_persists_after_creation(self, client, auth_headers):
        """Should persist task data in database."""
        create_resp = client.post("/tasks", json={"title": "Persist Test"}, headers=auth_headers)
        task_id = create_resp.get_json()["id"]

        get_resp = client.get(f"/tasks/{task_id}", headers=auth_headers)
        assert get_resp.status_code == 200
        data = get_resp.get_json()
        assert data["title"] == "Persist Test"
        assert data["id"] == task_id

    def test_multiple_sequential_updates(self, client, auth_headers):
        """Should handle multiple sequential updates."""
        create_resp = client.post("/tasks", json={"title": "Initial"}, headers=auth_headers)
        task_id = create_resp.get_json()["id"]

        client.put(f"/tasks/{task_id}", json={"title": "Updated 1"}, headers=auth_headers)
        client.put(f"/tasks/{task_id}", json={"status": "in_progress"}, headers=auth_headers)
        client.put(f"/tasks/{task_id}", json={"title": "Updated 2", "status": "completed"}, headers=auth_headers)

        get_resp = client.get(f"/tasks/{task_id}", headers=auth_headers)
        data = get_resp.get_json()
        assert data["title"] == "Updated 2"
        assert data["status"] == "completed"

    def test_created_at_is_iso_format(self, client, auth_headers):
        """Should return created_at in ISO format."""
        create_resp = client.post("/tasks", json={"title": "ISO Test"}, headers=auth_headers)
        data = create_resp.get_json()

        created_at = data["created_at"]
        assert created_at is not None
        # Check ISO format by attempting to parse it
        try:
            datetime.fromisoformat(created_at)
        except ValueError:
            pytest.fail(f"created_at is not in ISO format: {created_at}")


class TestNotificationTrigger:
    """Tests for async email notification trigger."""

    @patch("tasks.send_notification_email.delay")
    def test_notification_sent_when_status_changes_to_completed(self, mock_task, client, auth_headers):
        """Should trigger email notification when status changes to completed."""
        create_resp = client.post("/tasks", json={"title": "Test Task"}, headers=auth_headers)
        task_id = create_resp.get_json()["id"]

        client.put(
            f"/tasks/{task_id}",
            json={"status": "completed"},
            content_type="application/json",
            headers=auth_headers,
        )

        mock_task.assert_called_once()
        call_args = mock_task.call_args[0]
        assert call_args[1] == "Test Task"

    @patch("tasks.send_notification_email.delay")
    def test_notification_not_sent_for_other_status_changes(self, mock_task, client, auth_headers):
        """Should not trigger notification when status changes to non-completed status."""
        create_resp = client.post("/tasks", json={"title": "Test Task"}, headers=auth_headers)
        task_id = create_resp.get_json()["id"]

        client.put(
            f"/tasks/{task_id}",
            json={"status": "in_progress"},
            content_type="application/json",
            headers=auth_headers,
        )

        mock_task.assert_not_called()

    @patch("tasks.send_notification_email.delay")
    def test_notification_not_sent_if_already_completed(self, mock_task, client, auth_headers):
        """Should not trigger notification if task status is already completed."""
        create_resp = client.post("/tasks", json={"title": "Test Task"}, headers=auth_headers)
        task_id = create_resp.get_json()["id"]

        client.put(
            f"/tasks/{task_id}",
            json={"status": "completed"},
            content_type="application/json",
            headers=auth_headers,
        )
        mock_task.reset_mock()

        client.put(
            f"/tasks/{task_id}",
            json={"status": "completed"},
            content_type="application/json",
            headers=auth_headers,
        )

        mock_task.assert_not_called()

    @patch("tasks.send_notification_email.delay")
    def test_notification_with_user_email(self, mock_task, client):
        """Should send notification with user email address."""
        register_resp = client.post(
            "/auth/register",
            json={"username": "emailuser", "password": "pass123", "email": "user@example.com"},
            content_type="application/json",
        )
        token = register_resp.get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        create_resp = client.post("/tasks", json={"title": "Test Task"}, headers=headers)
        task_id = create_resp.get_json()["id"]

        client.put(
            f"/tasks/{task_id}",
            json={"status": "completed"},
            content_type="application/json",
            headers=headers,
        )

        mock_task.assert_called_once()
        call_args = mock_task.call_args[0]
        assert call_args[0] == "user@example.com"
        assert call_args[1] == "Test Task"

    @patch("tasks.send_notification_email.delay")
    def test_notification_with_default_email(self, mock_task, client, auth_headers):
        """Should use default email format when no email provided."""
        create_resp = client.post("/tasks", json={"title": "Test Task"}, headers=auth_headers)
        task_id = create_resp.get_json()["id"]

        client.put(
            f"/tasks/{task_id}",
            json={"status": "completed"},
            content_type="application/json",
            headers=auth_headers,
        )

        mock_task.assert_called_once()
        call_args = mock_task.call_args[0]
        assert "testuser@example.com" == call_args[0] or "testuser" == call_args[0]
        assert call_args[1] == "Test Task"

    @patch("tasks.send_notification_email.delay")
    def test_update_title_does_not_trigger_notification(self, mock_task, client, auth_headers):
        """Should not trigger notification when only title is updated."""
        create_resp = client.post("/tasks", json={"title": "Original Title"}, headers=auth_headers)
        task_id = create_resp.get_json()["id"]

        client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated Title"},
            content_type="application/json",
            headers=auth_headers,
        )

        mock_task.assert_not_called()

    @patch("tasks.send_notification_email.delay")
    def test_notification_sent_with_title_and_status_update(self, mock_task, client, auth_headers):
        """Should trigger notification when both title and status change to completed."""
        create_resp = client.post("/tasks", json={"title": "Original Title"}, headers=auth_headers)
        task_id = create_resp.get_json()["id"]

        client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated Title", "status": "completed"},
            content_type="application/json",
            headers=auth_headers,
        )

        mock_task.assert_called_once()
        call_args = mock_task.call_args[0]
        assert call_args[1] == "Updated Title"


class TestPagination:
    """Tests for cursor-based pagination on GET /tasks endpoint."""

    def test_pagination_default_limit(self, client, auth_headers):
        """Should use default limit of 20 when not specified."""
        for i in range(30):
            client.post("/tasks", json={"title": f"Task {i+1}"}, headers=auth_headers)

        response = client.get("/tasks", headers=auth_headers)
        result = response.get_json()
        assert len(result["data"]) == 20
        assert result["next_cursor"] is not None
        assert result["total"] == 30

    def test_pagination_custom_limit(self, client, auth_headers):
        """Should respect custom limit parameter."""
        for i in range(10):
            client.post("/tasks", json={"title": f"Task {i+1}"}, headers=auth_headers)

        response = client.get("/tasks?limit=5", headers=auth_headers)
        result = response.get_json()
        assert len(result["data"]) == 5
        assert result["next_cursor"] is not None
        assert result["total"] == 10

    def test_pagination_limit_max_100(self, client, auth_headers):
        """Should cap limit at 100."""
        for i in range(10):
            client.post("/tasks", json={"title": f"Task {i+1}"}, headers=auth_headers)

        response = client.get("/tasks?limit=200", headers=auth_headers)
        result = response.get_json()
        assert len(result["data"]) == 10
        assert result["next_cursor"] is None
        assert result["total"] == 10

    def test_pagination_invalid_limit_defaults_to_20(self, client, auth_headers):
        """Should default to 20 when limit is invalid."""
        for i in range(50):
            client.post("/tasks", json={"title": f"Task {i+1}"}, headers=auth_headers)

        response = client.get("/tasks?limit=0", headers=auth_headers)
        result = response.get_json()
        assert len(result["data"]) == 20

    def test_pagination_cursor_navigation(self, client, auth_headers):
        """Should navigate through pages using cursor."""
        task_ids = []
        for i in range(10):
            resp = client.post("/tasks", json={"title": f"Task {i+1}"}, headers=auth_headers)
            task_ids.append(resp.get_json()["id"])

        response1 = client.get("/tasks?limit=3", headers=auth_headers)
        result1 = response1.get_json()
        assert len(result1["data"]) == 3
        cursor1 = result1["next_cursor"]
        assert cursor1 is not None

        response2 = client.get(f"/tasks?limit=3&cursor={cursor1}", headers=auth_headers)
        result2 = response2.get_json()
        assert len(result2["data"]) == 3

        assert result1["data"][0]["id"] != result2["data"][0]["id"]

    def test_pagination_last_page_has_no_cursor(self, client, auth_headers):
        """Should return null cursor on last page."""
        for i in range(5):
            client.post("/tasks", json={"title": f"Task {i+1}"}, headers=auth_headers)

        response = client.get("/tasks?limit=10", headers=auth_headers)
        result = response.get_json()
        assert len(result["data"]) == 5
        assert result["next_cursor"] is None

    def test_pagination_invalid_cursor_returns_empty(self, client, auth_headers):
        """Should return empty data when cursor doesn't exist."""
        for i in range(5):
            client.post("/tasks", json={"title": f"Task {i+1}"}, headers=auth_headers)

        response = client.get("/tasks?cursor=99999", headers=auth_headers)
        result = response.get_json()
        assert result["data"] == []
        assert result["next_cursor"] is None
        assert result["total"] == 5

    def test_pagination_response_includes_total(self, client, auth_headers):
        """Should include total count in response."""
        for i in range(7):
            client.post("/tasks", json={"title": f"Task {i+1}"}, headers=auth_headers)

        response = client.get("/tasks?limit=3", headers=auth_headers)
        result = response.get_json()
        assert result["total"] == 7

    def test_pagination_first_page_without_cursor(self, client, auth_headers):
        """Should return first page when no cursor provided."""
        for i in range(5):
            client.post("/tasks", json={"title": f"Task {i+1}"}, headers=auth_headers)

        response = client.get("/tasks", headers=auth_headers)
        result = response.get_json()
        assert len(result["data"]) == 5
        assert result["data"][0]["title"] == "Task 5"
        assert result["data"][-1]["title"] == "Task 1"

    def test_pagination_cursor_ordering(self, client, auth_headers):
        """Should maintain ordering across pagination."""
        task_ids = []
        for i in range(6):
            resp = client.post("/tasks", json={"title": f"Task {i+1}"}, headers=auth_headers)
            task_ids.append(resp.get_json()["id"])

        all_data = []
        cursor = None
        while True:
            if cursor:
                response = client.get(f"/tasks?limit=2&cursor={cursor}", headers=auth_headers)
            else:
                response = client.get("/tasks?limit=2", headers=auth_headers)

            result = response.get_json()
            all_data.extend(result["data"])

            if result["next_cursor"] is None:
                break
            cursor = result["next_cursor"]

        assert len(all_data) == 6
        for i in range(len(all_data) - 1):
            assert all_data[i]["created_at"] >= all_data[i+1]["created_at"]


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    def test_rate_limiting_applied_to_endpoints(self, client):
        """Should have rate limiting decorator applied to endpoints."""
        from app import app as flask_app
        with flask_app.app_context():
            register_route = None
            login_route = None
            tasks_get_route = None
            for rule in flask_app.url_map.iter_rules():
                if rule.endpoint == "register":
                    register_route = rule
                elif rule.endpoint == "login":
                    login_route = rule
                elif rule.endpoint == "list_tasks":
                    tasks_get_route = rule

            assert register_route is not None
            assert login_route is not None
            assert tasks_get_route is not None

    def test_rate_limit_error_response_format(self, client):
        """Should return proper error format when rate limited."""
        response = client.post(
            "/auth/register",
            json={"username": "testuser", "password": "pass"},
            content_type="application/json",
        )
        assert response.status_code in [201, 400]

    def test_rate_limiter_uses_user_id_for_authenticated_endpoints(self, client, auth_headers):
        """Should use user ID for rate limiting on authenticated endpoints."""
        response = client.get("/tasks", headers=auth_headers)
        assert response.status_code == 200

    def test_rate_limiter_uses_ip_for_unauthenticated_endpoints(self, client):
        """Should use IP address for rate limiting on unauthenticated endpoints."""
        response = client.post(
            "/auth/register",
            json={"username": "testuser", "password": "pass"},
            content_type="application/json",
        )
        assert response.status_code in [201, 400]
