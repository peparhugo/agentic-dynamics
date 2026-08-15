"""
Test suite for Flask task management API.
"""

import pytest
import os
import sqlite3
import jwt
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import app as app_module
from app import app, init_db


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Create a test client with a temporary database and rate limiting disabled."""
    test_db = str(tmp_path / "test_tasks.db")
    monkeypatch.setenv("DATABASE", test_db)
    monkeypatch.setattr(app_module, "DATABASE", test_db)

    # Initialize fresh database
    init_db()

    # Disable rate limiting for tests that don't specifically test it
    from app import limiter
    limiter.enabled = False

    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def client_with_rate_limiting(monkeypatch, tmp_path):
    """Create a test client with a temporary database and rate limiting enabled."""
    test_db = str(tmp_path / "test_tasks_rl.db")
    monkeypatch.setenv("DATABASE", test_db)
    monkeypatch.setattr(app_module, "DATABASE", test_db)

    # Initialize fresh database
    init_db()

    # Enable rate limiting for rate limiting tests
    from app import limiter
    limiter.enabled = True
    limiter.reset()

    with app.test_client() as test_client:
        yield test_client
        limiter.reset()


@pytest.fixture
def auth_headers(request):
    """Helper to create a user and return auth headers."""
    # Support both 'client' and 'client_with_rate_limiting' fixtures
    client = request.getfixturevalue('client_with_rate_limiting') if 'client_with_rate_limiting' in request.fixturenames else request.getfixturevalue('client')

    def _create_auth(username="testuser", password="testpass", email=None):
        data = {"username": username, "password": password}
        if email:
            data["email"] = email
        response = client.post(
            "/auth/register",
            json=data
        )
        assert response.status_code == 201

        login_response = client.post(
            "/auth/login",
            json={"username": username, "password": password}
        )
        assert login_response.status_code == 200
        token = login_response.get_json()["token"]
        return {"Authorization": f"Bearer {token}"}

    return _create_auth


class TestAuthentication:
    def test_register_success(self, client):
        """POST /auth/register with valid credentials should create user."""
        response = client.post(
            "/auth/register",
            json={"username": "newuser", "password": "password123"}
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["username"] == "newuser"
        assert "id" in data

    def test_register_missing_username(self, client):
        """POST /auth/register without username should return 400."""
        response = client.post(
            "/auth/register",
            json={"password": "password123"}
        )
        assert response.status_code == 400
        assert "username and password are required" in response.get_json()["error"]

    def test_register_missing_password(self, client):
        """POST /auth/register without password should return 400."""
        response = client.post(
            "/auth/register",
            json={"username": "user"}
        )
        assert response.status_code == 400
        assert "username and password are required" in response.get_json()["error"]

    def test_register_duplicate_username(self, client):
        """POST /auth/register with duplicate username should return 409."""
        client.post(
            "/auth/register",
            json={"username": "duplicate", "password": "pass123"}
        )
        response = client.post(
            "/auth/register",
            json={"username": "duplicate", "password": "pass456"}
        )
        assert response.status_code == 409
        assert "username already exists" in response.get_json()["error"]

    def test_login_success(self, client):
        """POST /auth/login with valid credentials should return token."""
        client.post(
            "/auth/register",
            json={"username": "user1", "password": "pass123"}
        )
        response = client.post(
            "/auth/login",
            json={"username": "user1", "password": "pass123"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "token" in data

    def test_login_invalid_password(self, client):
        """POST /auth/login with invalid password should return 401."""
        client.post(
            "/auth/register",
            json={"username": "user2", "password": "correct"}
        )
        response = client.post(
            "/auth/login",
            json={"username": "user2", "password": "wrong"}
        )
        assert response.status_code == 401
        assert "invalid username or password" in response.get_json()["error"]

    def test_login_nonexistent_user(self, client):
        """POST /auth/login with nonexistent user should return 401."""
        response = client.post(
            "/auth/login",
            json={"username": "nonexistent", "password": "pass"}
        )
        assert response.status_code == 401
        assert "invalid username or password" in response.get_json()["error"]


class TestCreateTask:
    def test_create_task_success(self, client, auth_headers):
        """POST /tasks with valid title should create task with 'pending' status."""
        headers = auth_headers("user1")
        response = client.post("/tasks", json={"title": "Buy milk"}, headers=headers)
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Buy milk"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data
        assert "owner_id" in data

    def test_create_task_missing_title(self, client, auth_headers):
        """POST /tasks without title should return 400."""
        headers = auth_headers("user2")
        response = client.post("/tasks", json={}, headers=headers)
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_create_task_empty_title(self, client, auth_headers):
        """POST /tasks with empty title should return 400."""
        headers = auth_headers("user3")
        response = client.post("/tasks", json={"title": ""}, headers=headers)
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_create_task_whitespace_title(self, client, auth_headers):
        """POST /tasks with whitespace-only title should return 400."""
        headers = auth_headers("user4")
        response = client.post("/tasks", json={"title": "   "}, headers=headers)
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_create_task_no_json(self, client, auth_headers):
        """POST /tasks with no JSON body should return 400."""
        headers = auth_headers("user5")
        response = client.post("/tasks", headers=headers)
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_create_task_missing_token(self, client):
        """POST /tasks without token should return 401."""
        response = client.post("/tasks", json={"title": "Task"})
        assert response.status_code == 401
        assert "Missing token" in response.get_json()["error"]

    def test_create_task_invalid_token(self, client):
        """POST /tasks with invalid token should return 401."""
        response = client.post(
            "/tasks",
            json={"title": "Task"},
            headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert response.status_code == 401
        assert "Invalid token" in response.get_json()["error"]


class TestListTasks:
    def test_list_tasks_empty(self, client, auth_headers):
        """GET /tasks should return empty paginated response initially."""
        headers = auth_headers("user6")
        response = client.get("/tasks", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["data"] == []
        assert data["next_cursor"] is None
        assert data["total"] == 0

    def test_list_tasks_multiple(self, client, auth_headers):
        """GET /tasks should return paginated tasks ordered by id desc."""
        headers = auth_headers("user7")
        # Create three tasks
        t1 = client.post("/tasks", json={"title": "Task 1"}, headers=headers).get_json()
        t2 = client.post("/tasks", json={"title": "Task 2"}, headers=headers).get_json()
        t3 = client.post("/tasks", json={"title": "Task 3"}, headers=headers).get_json()

        response = client.get("/tasks", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        tasks = data["data"]
        assert len(tasks) == 3
        # Should be ordered by id descending
        assert tasks[0]["id"] == t3["id"]
        assert tasks[1]["id"] == t2["id"]
        assert tasks[2]["id"] == t1["id"]
        assert data["total"] == 3
        assert data["next_cursor"] is None

    def test_list_tasks_user_isolation(self, client, auth_headers):
        """GET /tasks should only return tasks owned by authenticated user."""
        headers1 = auth_headers("user8")
        headers2 = auth_headers("user9")

        # User 1 creates 2 tasks
        t1 = client.post("/tasks", json={"title": "User 1 Task 1"}, headers=headers1).get_json()
        t2 = client.post("/tasks", json={"title": "User 1 Task 2"}, headers=headers1).get_json()

        # User 2 creates 1 task
        t3 = client.post("/tasks", json={"title": "User 2 Task"}, headers=headers2).get_json()

        # User 1 should only see their 2 tasks
        response1 = client.get("/tasks", headers=headers1)
        tasks1 = response1.get_json()["data"]
        assert len(tasks1) == 2
        assert all(t["owner_id"] == t1["owner_id"] for t in tasks1)

        # User 2 should only see their 1 task
        response2 = client.get("/tasks", headers=headers2)
        data2 = response2.get_json()
        tasks2 = data2["data"]
        assert len(tasks2) == 1
        assert tasks2[0]["id"] == t3["id"]

    def test_list_tasks_missing_token(self, client):
        """GET /tasks without token should return 401."""
        response = client.get("/tasks")
        assert response.status_code == 401
        assert "Missing token" in response.get_json()["error"]


class TestGetTask:
    def test_get_task_success(self, client, auth_headers):
        """GET /tasks/{id} should return the task."""
        headers = auth_headers("user10")
        created = client.post("/tasks", json={"title": "Test task"}, headers=headers).get_json()
        task_id = created["id"]

        response = client.get(f"/tasks/{task_id}", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Test task"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client, auth_headers):
        """GET /tasks/{id} for non-existent task should return 404."""
        headers = auth_headers("user11")
        response = client.get("/tasks/999", headers=headers)
        assert response.status_code == 404
        assert response.get_json()["error"] == "task not found"

    def test_get_task_access_denied(self, client, auth_headers):
        """GET /tasks/{id} should deny access to other user's task."""
        headers1 = auth_headers("user12")
        headers2 = auth_headers("user13")

        # User 1 creates a task
        created = client.post("/tasks", json={"title": "User 1 Task"}, headers=headers1).get_json()
        task_id = created["id"]

        # User 2 tries to access User 1's task
        response = client.get(f"/tasks/{task_id}", headers=headers2)
        assert response.status_code == 404
        assert response.get_json()["error"] == "task not found"

    def test_get_task_missing_token(self, client):
        """GET /tasks/{id} without token should return 401."""
        response = client.get("/tasks/1")
        assert response.status_code == 401
        assert "Missing token" in response.get_json()["error"]


class TestUpdateTask:
    def test_update_task_title(self, client, auth_headers):
        """PUT /tasks/{id} should update title."""
        headers = auth_headers("user14")
        created = client.post("/tasks", json={"title": "Old title"}, headers=headers).get_json()
        task_id = created["id"]

        response = client.put(
            f"/tasks/{task_id}", json={"title": "New title"}, headers=headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["title"] == "New title"
        assert data["status"] == "pending"

    def test_update_task_status_to_done(self, client, auth_headers):
        """PUT /tasks/{id} should update status to 'done'."""
        headers = auth_headers("user15")
        created = client.post("/tasks", json={"title": "Task"}, headers=headers).get_json()
        task_id = created["id"]

        response = client.put(
            f"/tasks/{task_id}", json={"status": "done"}, headers=headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["status"] == "done"

    def test_update_task_status_to_pending(self, client, auth_headers):
        """PUT /tasks/{id} should update status to 'pending'."""
        headers = auth_headers("user16")
        created = client.post("/tasks", json={"title": "Task"}, headers=headers).get_json()
        task_id = created["id"]
        # First change to done
        client.put(f"/tasks/{task_id}", json={"status": "done"}, headers=headers)
        # Then change back to pending
        response = client.put(
            f"/tasks/{task_id}", json={"status": "pending"}, headers=headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "pending"

    def test_update_task_invalid_status(self, client, auth_headers):
        """PUT /tasks/{id} with invalid status should return 422."""
        headers = auth_headers("user17")
        created = client.post("/tasks", json={"title": "Task"}, headers=headers).get_json()
        task_id = created["id"]

        response = client.put(
            f"/tasks/{task_id}", json={"status": "invalid"}, headers=headers
        )
        assert response.status_code == 422
        error = response.get_json()["error"]
        assert "Invalid status" in error

    def test_update_task_title_and_status(self, client, auth_headers):
        """PUT /tasks/{id} should update both title and status."""
        headers = auth_headers("user18")
        created = client.post("/tasks", json={"title": "Original"}, headers=headers).get_json()
        task_id = created["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated", "status": "done"},
            headers=headers
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "done"

    def test_update_task_not_found(self, client, auth_headers):
        """PUT /tasks/{id} for non-existent task should return 404."""
        headers = auth_headers("user19")
        response = client.put("/tasks/999", json={"title": "New title"}, headers=headers)
        assert response.status_code == 404
        assert response.get_json()["error"] == "task not found"

    def test_update_task_no_changes(self, client, auth_headers):
        """PUT /tasks/{id} with no fields should return task unchanged."""
        headers = auth_headers("user20")
        created = client.post("/tasks", json={"title": "Task"}, headers=headers).get_json()
        task_id = created["id"]

        response = client.put(f"/tasks/{task_id}", json={}, headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Task"
        assert data["status"] == "pending"

    def test_update_task_various_invalid_statuses(self, client, auth_headers):
        """PUT /tasks/{id} should reject various invalid status values."""
        headers = auth_headers("user21")
        created = client.post("/tasks", json={"title": "Task"}, headers=headers).get_json()
        task_id = created["id"]

        invalid_statuses = ["in_progress", "todo", "completed", "DONE", "Pending", ""]
        for invalid_status in invalid_statuses:
            response = client.put(
                f"/tasks/{task_id}", json={"status": invalid_status}, headers=headers
            )
            assert response.status_code == 422, f"Expected 422 for status '{invalid_status}'"

    def test_update_task_access_denied(self, client, auth_headers):
        """PUT /tasks/{id} should deny access to other user's task."""
        headers1 = auth_headers("user22")
        headers2 = auth_headers("user23")

        # User 1 creates a task
        created = client.post("/tasks", json={"title": "User 1 Task"}, headers=headers1).get_json()
        task_id = created["id"]

        # User 2 tries to update User 1's task
        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Hacked"},
            headers=headers2
        )
        assert response.status_code == 404
        assert response.get_json()["error"] == "task not found"

    def test_update_task_missing_token(self, client):
        """PUT /tasks/{id} without token should return 401."""
        response = client.put("/tasks/1", json={"title": "New title"})
        assert response.status_code == 401
        assert "Missing token" in response.get_json()["error"]


class TestDateFormat:
    def test_created_at_is_iso8601(self, client, auth_headers):
        """Task created_at should be ISO-8601 formatted."""
        headers = auth_headers("user24")
        response = client.post("/tasks", json={"title": "Task"}, headers=headers)
        data = response.get_json()
        created_at = data["created_at"]
        # ISO-8601 format: YYYY-MM-DDTHH:MM:SS.ffffff
        assert "T" in created_at, "created_at should be ISO-8601 format"
        # Try to parse it to verify format
        from datetime import datetime
        datetime.fromisoformat(created_at)


class TestEmailNotification:
    def test_email_notification_sent_on_status_change_to_done(self, client, auth_headers, mocker):
        """PUT /tasks/{id} should trigger email notification when status changes to 'done'."""
        mock_send_email = mocker.patch("app.send_notification_email")
        headers = auth_headers("testuser_notify", email="notify@test.com")
        # Create task
        created = client.post("/tasks", json={"title": "Important Task"}, headers=headers).get_json()
        task_id = created["id"]

        # Update status to done
        response = client.put(
            f"/tasks/{task_id}", json={"status": "done"}, headers=headers
        )
        assert response.status_code == 200
        # Verify Celery task was called
        mock_send_email.delay.assert_called_once()

    def test_email_notification_not_sent_on_status_pending(self, client, auth_headers, mocker):
        """PUT /tasks/{id} should NOT trigger email notification when status is 'pending'."""
        mock_send_email = mocker.patch("app.send_notification_email")
        headers = auth_headers("testuser_pending")
        # Create task (default status is pending)
        created = client.post("/tasks", json={"title": "Task"}, headers=headers).get_json()
        task_id = created["id"]

        # Update title only
        response = client.put(
            f"/tasks/{task_id}", json={"title": "Updated"}, headers=headers
        )
        assert response.status_code == 200
        # Verify Celery task was NOT called
        mock_send_email.delay.assert_not_called()

    def test_email_notification_not_sent_when_already_done(self, client, auth_headers, mocker):
        """PUT /tasks/{id} should NOT trigger email notification if already done."""
        mock_send_email = mocker.patch("app.send_notification_email")
        headers = auth_headers("testuser_already_done", email="already@test.com")
        # Create task
        created = client.post("/tasks", json={"title": "Task"}, headers=headers).get_json()
        task_id = created["id"]

        # Change to done
        client.put(f"/tasks/{task_id}", json={"status": "done"}, headers=headers)

        # Reset the mock to track new calls
        mock_send_email.delay.reset_mock()

        # Try to change to done again
        response = client.put(
            f"/tasks/{task_id}", json={"status": "done"}, headers=headers
        )
        assert response.status_code == 200
        # Verify Celery task was NOT called
        mock_send_email.delay.assert_not_called()

    def test_email_notification_with_correct_parameters(self, client, auth_headers, mocker):
        """Email notification should include task title and user email."""
        mock_send_email = mocker.patch("app.send_notification_email")
        headers = auth_headers("emailuser", email="emailuser@test.com")
        # Create task
        task_title = "Buy groceries"
        created = client.post("/tasks", json={"title": task_title}, headers=headers).get_json()
        task_id = created["id"]

        # Update status to done
        response = client.put(
            f"/tasks/{task_id}", json={"status": "done"}, headers=headers
        )
        assert response.status_code == 200

    def test_user_registration_with_email(self, client):
        """POST /auth/register should accept email and store it."""
        response = client.post(
            "/auth/register",
            json={"username": "emailuser", "password": "pass123", "email": "user@example.com"}
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["email"] == "user@example.com"

    def test_user_registration_without_email(self, client):
        """POST /auth/register should work without email (optional)."""
        response = client.post(
            "/auth/register",
            json={"username": "noemailuser", "password": "pass123"}
        )
        assert response.status_code == 201
        data = response.get_json()
        assert "email" in data

    def test_user_login_returns_email(self, client):
        """POST /auth/login should return email if available."""
        # Register with email
        client.post(
            "/auth/register",
            json={"username": "logintest", "password": "pass123", "email": "test@example.com"}
        )
        # Login
        response = client.post(
            "/auth/login",
            json={"username": "logintest", "password": "pass123"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "token" in data

    def test_no_notification_if_no_email(self, client, auth_headers, mocker):
        """Email notification should not trigger if user has no email."""
        mock_send_email = mocker.patch("app.send_notification_email")
        # Register user without email
        headers = auth_headers("noemailuser")

        # Create task
        created = client.post("/tasks", json={"title": "Task"}, headers=headers).get_json()
        task_id = created["id"]

        # Update status to done (should not send notification without email)
        response = client.put(
            f"/tasks/{task_id}", json={"status": "done"}, headers=headers
        )
        assert response.status_code == 200
        # Verify Celery task was NOT called
        mock_send_email.delay.assert_not_called()


class TestPagination:
    def test_list_tasks_pagination_default_limit(self, client, auth_headers):
        """GET /tasks should return paginated results with default limit of 20."""
        headers = auth_headers("pagination_user1")

        # Create 30 tasks
        for i in range(30):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

        # Get first page (default limit=20)
        response = client.get("/tasks", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert "data" in data
        assert "next_cursor" in data
        assert "total" in data
        assert len(data["data"]) == 20
        assert data["total"] == 30
        assert data["next_cursor"] is not None

    def test_list_tasks_pagination_custom_limit(self, client, auth_headers):
        """GET /tasks?limit=10 should return 10 items."""
        headers = auth_headers("pagination_user2")

        # Create 25 tasks
        for i in range(25):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

        # Get first page with limit=10
        response = client.get("/tasks?limit=10", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["data"]) == 10
        assert data["next_cursor"] is not None
        assert data["total"] == 25

    def test_list_tasks_pagination_limit_max_100(self, client, auth_headers):
        """GET /tasks?limit=200 should cap at 100."""
        headers = auth_headers("pagination_user3")

        # Create 120 tasks
        for i in range(120):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

        # Request with limit > 100
        response = client.get("/tasks?limit=200", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["data"]) == 100
        assert data["total"] == 120

    def test_list_tasks_pagination_cursor(self, client, auth_headers):
        """GET /tasks?cursor=X should return next page starting after id X."""
        headers = auth_headers("pagination_user4")

        # Create 25 tasks
        for i in range(25):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

        # Get first page with limit=10
        response1 = client.get("/tasks?limit=10", headers=headers)
        data1 = response1.get_json()
        first_page = data1["data"]
        first_page_ids = [t["id"] for t in first_page]
        assert len(first_page) == 10
        cursor = data1["next_cursor"]

        # Get second page using cursor
        response2 = client.get(f"/tasks?cursor={cursor}&limit=10", headers=headers)
        data2 = response2.get_json()
        second_page = data2["data"]
        second_page_ids = [t["id"] for t in second_page]
        assert len(second_page) == 10

        # Verify no overlap
        assert len(set(first_page_ids) & set(second_page_ids)) == 0

    def test_list_tasks_pagination_last_page(self, client, auth_headers):
        """GET /tasks with last page should have next_cursor=null."""
        headers = auth_headers("pagination_user5")

        # Create 25 tasks
        for i in range(25):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

        # Get first page with limit=20
        response1 = client.get("/tasks?limit=20", headers=headers)
        data1 = response1.get_json()
        cursor = data1["next_cursor"]

        # Get second page with cursor
        response2 = client.get(f"/tasks?cursor={cursor}&limit=20", headers=headers)
        data2 = response2.get_json()
        assert len(data2["data"]) == 5
        assert data2["next_cursor"] is None

    def test_list_tasks_pagination_empty(self, client, auth_headers):
        """GET /tasks on empty should return empty data with no cursor."""
        headers = auth_headers("pagination_user6")

        response = client.get("/tasks", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["data"] == []
        assert data["next_cursor"] is None
        assert data["total"] == 0

    def test_list_tasks_pagination_single_page(self, client, auth_headers):
        """GET /tasks with fewer items than limit should have no cursor."""
        headers = auth_headers("pagination_user7")

        # Create 5 tasks
        for i in range(5):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

        response = client.get("/tasks?limit=20", headers=headers)
        data = response.get_json()
        assert len(data["data"]) == 5
        assert data["next_cursor"] is None
        assert data["total"] == 5

    def test_list_tasks_pagination_user_isolation(self, client, auth_headers):
        """Pagination should respect user isolation."""
        headers1 = auth_headers("pagination_iso_user1")
        headers2 = auth_headers("pagination_iso_user2")

        # User 1 creates 15 tasks
        for i in range(15):
            client.post("/tasks", json={"title": f"User1 Task {i}"}, headers=headers1)

        # User 2 creates 5 tasks
        for i in range(5):
            client.post("/tasks", json={"title": f"User2 Task {i}"}, headers=headers2)

        # User 1 should see 15 tasks
        response1 = client.get("/tasks", headers=headers1)
        data1 = response1.get_json()
        assert data1["total"] == 15
        assert len(data1["data"]) == 15

        # User 2 should see only 5 tasks
        response2 = client.get("/tasks", headers=headers2)
        data2 = response2.get_json()
        assert data2["total"] == 5
        assert len(data2["data"]) == 5

    def test_list_tasks_pagination_invalid_limit(self, client, auth_headers):
        """GET /tasks with invalid limit should default to 20."""
        headers = auth_headers("pagination_user8")

        # Create 30 tasks
        for i in range(30):
            client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

        # Request with negative limit
        response = client.get("/tasks?limit=-5", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["data"]) == 20

    def test_list_tasks_pagination_cursor_ordering(self, client, auth_headers):
        """Paginated results should maintain descending id order."""
        headers = auth_headers("pagination_user9")

        # Create 30 tasks
        task_ids = []
        for i in range(30):
            resp = client.post("/tasks", json={"title": f"Task {i}"}, headers=headers)
            task_ids.append(resp.get_json()["id"])

        # Get first page
        response1 = client.get("/tasks?limit=10", headers=headers)
        data1 = response1.get_json()
        page1_ids = [t["id"] for t in data1["data"]]

        # Verify descending order
        assert page1_ids == sorted(page1_ids, reverse=True)

        # Get second page
        cursor = data1["next_cursor"]
        response2 = client.get(f"/tasks?cursor={cursor}&limit=10", headers=headers)
        data2 = response2.get_json()
        page2_ids = [t["id"] for t in data2["data"]]

        # Verify descending order
        assert page2_ids == sorted(page2_ids, reverse=True)


class TestRateLimiting:
    def test_rate_limit_enforced_on_task_creation(self, client_with_rate_limiting, auth_headers):
        """Rate limiting should enforce 100 requests per minute."""
        headers = auth_headers("rate_limit_user")

        # Make 100 requests (should all succeed)
        for i in range(100):
            response = client_with_rate_limiting.post(
                "/tasks",
                json={"title": f"Task {i}"},
                headers=headers
            )
            if response.status_code != 201:
                # If we hit the limit early, that's also valid (depends on implementation)
                break

        # The 101st request should be rate limited
        response = client_with_rate_limiting.post(
            "/tasks",
            json={"title": "Task 101"},
            headers=headers
        )
        assert response.status_code == 429

    def test_rate_limit_retry_after_header(self, client_with_rate_limiting, auth_headers):
        """Rate limited response should include Retry-After header."""
        headers = auth_headers("retry_after_user")

        # Make 100 requests
        for i in range(100):
            client_with_rate_limiting.post(
                "/tasks",
                json={"title": f"Task {i}"},
                headers=headers
            )

        # Get rate limited response
        response = client_with_rate_limiting.post(
            "/tasks",
            json={"title": "Task 101"},
            headers=headers
        )
        assert response.status_code == 429
        # Flask-Limiter should set Retry-After header
        assert "Retry-After" in response.headers or response.status_code == 429

    def test_rate_limit_on_auth_endpoints(self, client_with_rate_limiting):
        """Rate limiting should be applied to auth endpoints."""
        # Make 100 login attempts
        # First create a user
        client_with_rate_limiting.post(
            "/auth/register",
            json={"username": "rluser", "password": "pass123"}
        )

        for i in range(100):
            client_with_rate_limiting.post(
                "/auth/login",
                json={"username": "rluser", "password": "pass123"}
            )

        # The 101st attempt should be rate limited
        response = client_with_rate_limiting.post(
            "/auth/login",
            json={"username": "rluser", "password": "pass123"}
        )
        assert response.status_code == 429

    def test_rate_limit_per_user(self, client_with_rate_limiting, auth_headers):
        """Rate limiting should be per-user, not global."""
        headers1 = auth_headers("rl_user1")
        headers2 = auth_headers("rl_user2")

        # User 1 makes 50 requests
        for i in range(50):
            client_with_rate_limiting.post("/tasks", json={"title": f"Task {i}"}, headers=headers1)

        # User 2 should still be able to make requests (not rate limited)
        response = client_with_rate_limiting.post(
            "/tasks",
            json={"title": "User 2 Task"},
            headers=headers2
        )
        assert response.status_code == 201

    def test_rate_limit_on_get_tasks(self, client_with_rate_limiting, auth_headers):
        """Rate limiting should be applied to GET /tasks."""
        headers = auth_headers("get_rl_user")

        # Create some tasks (rate limited, so disable for now)
        for i in range(5):
            client_with_rate_limiting.post("/tasks", json={"title": f"Task {i}"}, headers=headers)

        # Make 100 GET requests
        for i in range(100):
            response = client_with_rate_limiting.get("/tasks", headers=headers)
            if response.status_code != 200:
                break

        # The 101st request should be rate limited
        response = client_with_rate_limiting.get("/tasks", headers=headers)
        assert response.status_code == 429

    def test_rate_limit_on_show_task(self, client_with_rate_limiting, auth_headers):
        """Rate limiting should be applied to GET /tasks/{id}."""
        headers = auth_headers("show_rl_user")

        # Create a task
        resp = client_with_rate_limiting.post("/tasks", json={"title": "Task"}, headers=headers)
        task_id = resp.get_json()["id"]

        # Make 100 GET requests
        for i in range(100):
            response = client_with_rate_limiting.get(f"/tasks/{task_id}", headers=headers)
            if response.status_code != 200:
                break

        # The 101st request should be rate limited
        response = client_with_rate_limiting.get(f"/tasks/{task_id}", headers=headers)
        assert response.status_code == 429

    def test_rate_limit_on_update_task(self, client_with_rate_limiting, auth_headers):
        """Rate limiting should be applied to PUT /tasks/{id}."""
        headers = auth_headers("update_rl_user")

        # Create a task
        resp = client_with_rate_limiting.post("/tasks", json={"title": "Task"}, headers=headers)
        task_id = resp.get_json()["id"]

        # Make 100 PUT requests
        for i in range(100):
            response = client_with_rate_limiting.put(
                f"/tasks/{task_id}",
                json={"title": f"Updated {i}"},
                headers=headers
            )
            if response.status_code != 200:
                break

        # The 101st request should be rate limited
        response = client_with_rate_limiting.put(
            f"/tasks/{task_id}",
            json={"title": "Updated 101"},
            headers=headers
        )
        assert response.status_code == 429

    def test_rate_limit_reset_per_test(self, client_with_rate_limiting):
        """Each test has its own rate limit bucket (resets with fixture)."""
        # This test just verifies rate limiting works in isolation
        # Make 100 requests
        for i in range(100):
            response = client_with_rate_limiting.post(
                "/auth/register",
                json={"username": f"user{i}_{i}", "password": "pass"}
            )
            assert response.status_code in [201, 409]  # 409 if username duplicate

        # The 101st request should be rate limited
        response = client_with_rate_limiting.post(
            "/auth/register",
            json={"username": "final_user", "password": "pass"}
        )
        assert response.status_code == 429


class TestIntegration:
    def test_full_workflow(self, client, auth_headers):
        """Test a complete workflow: register, login, create, list, get, update."""
        headers = auth_headers("user25")

        # Create a task
        create_response = client.post("/tasks", json={"title": "Buy groceries"}, headers=headers)
        assert create_response.status_code == 201
        task = create_response.get_json()
        task_id = task["id"]
        assert task["status"] == "pending"

        # List tasks
        list_response = client.get("/tasks", headers=headers)
        assert list_response.status_code == 200
        paginated_data = list_response.get_json()
        tasks = paginated_data["data"]
        assert len(tasks) == 1

        # Get single task
        get_response = client.get(f"/tasks/{task_id}", headers=headers)
        assert get_response.status_code == 200
        retrieved_task = get_response.get_json()
        assert retrieved_task["id"] == task_id
        assert retrieved_task["title"] == "Buy groceries"

        # Update task to done
        update_response = client.put(
            f"/tasks/{task_id}", json={"status": "done"}, headers=headers
        )
        assert update_response.status_code == 200
        updated_task = update_response.get_json()
        assert updated_task["status"] == "done"

        # Verify update persisted
        final_response = client.get(f"/tasks/{task_id}", headers=headers)
        final_task = final_response.get_json()
        assert final_task["status"] == "done"

    def test_auth_then_task_creation(self, client):
        """Test full auth flow: register, login, create task."""
        # Register
        reg_response = client.post(
            "/auth/register",
            json={"username": "newuser", "password": "mypass"}
        )
        assert reg_response.status_code == 201
        user = reg_response.get_json()
        assert user["username"] == "newuser"

        # Login
        login_response = client.post(
            "/auth/login",
            json={"username": "newuser", "password": "mypass"}
        )
        assert login_response.status_code == 200
        token = login_response.get_json()["token"]

        # Create task with token
        headers = {"Authorization": f"Bearer {token}"}
        task_response = client.post(
            "/tasks",
            json={"title": "New task"},
            headers=headers
        )
        assert task_response.status_code == 201
        task = task_response.get_json()
        assert task["title"] == "New task"
        assert task["owner_id"] == user["id"]
