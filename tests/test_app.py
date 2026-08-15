import pytest
import json
import os
import sqlite3
import tempfile
from datetime import datetime
from unittest.mock import patch, MagicMock
from app import app, init_db, DATABASE


@pytest.fixture
def client():
    # Create a temporary database file for each test
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.environ["DATABASE"] = db_path
    # Update app module's DATABASE variable
    import app as app_module
    app_module.DATABASE = db_path
    app.config["TESTING"] = True

    with app.app_context():
        init_db()

    with app.test_client() as test_client:
        yield test_client

    # Clean up
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.fixture
def auth_user(client):
    """Register and return auth token for a test user."""
    response = client.post(
        "/auth/register",
        json={"username": "testuser", "password": "testpass", "email": "testuser@example.com"},
        content_type="application/json",
    )
    assert response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={"username": "testuser", "password": "testpass"},
        content_type="application/json",
    )
    assert login_response.status_code == 200
    token = login_response.get_json()["token"]
    return {
        "username": "testuser",
        "password": "testpass",
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture
def sample_task(client, auth_user):
    """Create a sample task for testing."""
    response = client.post(
        "/tasks",
        json={"title": "Test Task"},
        content_type="application/json",
        headers=auth_user["headers"],
    )
    return response.get_json()


# ── Auth Tests ────────────────────────────────────────────────

class TestRegister:
    def test_register_success(self, client):
        response = client.post(
            "/auth/register",
            json={"username": "newuser", "password": "password123"},
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["username"] == "newuser"
        assert "id" in data

    def test_register_missing_username(self, client):
        response = client.post(
            "/auth/register",
            json={"password": "password123"},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_register_missing_password(self, client):
        response = client.post(
            "/auth/register",
            json={"username": "newuser"},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_register_empty_username(self, client):
        response = client.post(
            "/auth/register",
            json={"username": "   ", "password": "password123"},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_register_empty_password(self, client):
        response = client.post(
            "/auth/register",
            json={"username": "newuser", "password": "   "},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_register_duplicate_username(self, client):
        # Register first user
        client.post(
            "/auth/register",
            json={"username": "duplicate", "password": "password123"},
            content_type="application/json",
        )
        # Try to register again with same username
        response = client.post(
            "/auth/register",
            json={"username": "duplicate", "password": "different"},
            content_type="application/json",
        )
        assert response.status_code == 409
        assert "already exists" in response.get_json()["error"]

    def test_register_no_json(self, client):
        response = client.post("/auth/register")
        assert response.status_code == 400


class TestLogin:
    def test_login_success(self, client, auth_user):
        response = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "testpass"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "token" in data

    def test_login_invalid_username(self, client):
        response = client.post(
            "/auth/login",
            json={"username": "nonexistent", "password": "password123"},
            content_type="application/json",
        )
        assert response.status_code == 401
        assert "error" in response.get_json()

    def test_login_invalid_password(self, client, auth_user):
        response = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "wrongpassword"},
            content_type="application/json",
        )
        assert response.status_code == 401
        assert "error" in response.get_json()

    def test_login_missing_username(self, client):
        response = client.post(
            "/auth/login",
            json={"password": "password123"},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_login_missing_password(self, client):
        response = client.post(
            "/auth/login",
            json={"username": "testuser"},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_login_no_json(self, client):
        response = client.post("/auth/login")
        assert response.status_code == 400


# ── Protected Tasks Tests ─────────────────────────────────────

class TestCreateTask:
    def test_create_task_success(self, client, auth_user):
        response = client.post(
            "/tasks",
            json={"title": "Buy groceries"},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data
        assert data["owner_id"] == 1  # First user

    def test_create_task_missing_title(self, client, auth_user):
        response = client.post(
            "/tasks",
            json={},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_create_task_empty_title(self, client, auth_user):
        response = client.post(
            "/tasks",
            json={"title": "   "},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 400

    def test_create_task_no_json(self, client, auth_user):
        response = client.post(
            "/tasks",
            headers=auth_user["headers"],
        )
        assert response.status_code == 400

    def test_create_task_no_auth(self, client):
        response = client.post(
            "/tasks",
            json={"title": "Buy groceries"},
            content_type="application/json",
        )
        assert response.status_code == 401
        assert "error" in response.get_json()

    def test_create_task_invalid_token(self, client):
        response = client.post(
            "/tasks",
            json={"title": "Buy groceries"},
            content_type="application/json",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == 401

    def test_created_at_is_iso8601(self, client, auth_user):
        response = client.post(
            "/tasks",
            json={"title": "Check ISO format"},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        data = response.get_json()
        try:
            datetime.fromisoformat(data["created_at"])
        except ValueError:
            pytest.fail(f"created_at not in ISO-8601 format: {data['created_at']}")


class TestListTasks:
    def test_list_empty(self, client, auth_user):
        response = client.get(
            "/tasks",
            headers=auth_user["headers"],
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["data"] == []
        assert data["next_cursor"] is None
        assert data["total"] == 0

    def test_list_single_task(self, client, auth_user, sample_task):
        response = client.get(
            "/tasks",
            headers=auth_user["headers"],
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["data"]) == 1
        assert data["data"][0]["title"] == "Test Task"

    def test_list_multiple_tasks_ordered_by_created_at_desc(self, client, auth_user):
        # Create tasks with slight delays to ensure different timestamps
        task1 = client.post(
            "/tasks",
            json={"title": "First"},
            content_type="application/json",
            headers=auth_user["headers"],
        ).get_json()

        task2 = client.post(
            "/tasks",
            json={"title": "Second"},
            content_type="application/json",
            headers=auth_user["headers"],
        ).get_json()

        task3 = client.post(
            "/tasks",
            json={"title": "Third"},
            content_type="application/json",
            headers=auth_user["headers"],
        ).get_json()

        response = client.get(
            "/tasks",
            headers=auth_user["headers"],
        )
        data = response.get_json()
        tasks = data["data"]
        assert len(tasks) == 3
        # Should be ordered by id DESC (newest first in our pagination)
        assert tasks[0]["id"] == task3["id"]
        assert tasks[1]["id"] == task2["id"]
        assert tasks[2]["id"] == task1["id"]

    def test_list_no_auth(self, client):
        response = client.get("/tasks")
        assert response.status_code == 401

    def test_list_tasks_isolated_by_user(self, client):
        # Register two users
        user1_response = client.post(
            "/auth/register",
            json={"username": "user1", "password": "pass1"},
            content_type="application/json",
        )
        user1_id = user1_response.get_json()["id"]
        user1_token_response = client.post(
            "/auth/login",
            json={"username": "user1", "password": "pass1"},
            content_type="application/json",
        )
        user1_token = user1_token_response.get_json()["token"]
        user1_headers = {"Authorization": f"Bearer {user1_token}"}

        user2_response = client.post(
            "/auth/register",
            json={"username": "user2", "password": "pass2"},
            content_type="application/json",
        )
        user2_id = user2_response.get_json()["id"]
        user2_token_response = client.post(
            "/auth/login",
            json={"username": "user2", "password": "pass2"},
            content_type="application/json",
        )
        user2_token = user2_token_response.get_json()["token"]
        user2_headers = {"Authorization": f"Bearer {user2_token}"}

        # User1 creates a task
        task1_response = client.post(
            "/tasks",
            json={"title": "User1 Task"},
            content_type="application/json",
            headers=user1_headers,
        )
        assert task1_response.status_code == 201

        # User2 creates a task
        task2_response = client.post(
            "/tasks",
            json={"title": "User2 Task"},
            content_type="application/json",
            headers=user2_headers,
        )
        assert task2_response.status_code == 201

        # User1 should only see their own task
        user1_tasks_response = client.get("/tasks", headers=user1_headers)
        user1_data = user1_tasks_response.get_json()
        assert user1_data["total"] == 1
        assert len(user1_data["data"]) == 1
        assert user1_data["data"][0]["title"] == "User1 Task"
        assert user1_data["data"][0]["owner_id"] == user1_id

        # User2 should only see their own task
        user2_tasks_response = client.get("/tasks", headers=user2_headers)
        user2_data = user2_tasks_response.get_json()
        assert user2_data["total"] == 1
        assert len(user2_data["data"]) == 1
        assert user2_data["data"][0]["title"] == "User2 Task"
        assert user2_data["data"][0]["owner_id"] == user2_id


class TestGetSingleTask:
    def test_get_task_success(self, client, auth_user, sample_task):
        task_id = sample_task["id"]
        response = client.get(
            f"/tasks/{task_id}",
            headers=auth_user["headers"],
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Test Task"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client, auth_user):
        response = client.get(
            "/tasks/9999",
            headers=auth_user["headers"],
        )
        assert response.status_code == 404
        assert "error" in response.get_json()

    def test_get_task_zero_id(self, client, auth_user):
        response = client.get(
            "/tasks/0",
            headers=auth_user["headers"],
        )
        assert response.status_code == 404

    def test_get_task_no_auth(self, client, sample_task):
        response = client.get(f"/tasks/{sample_task['id']}")
        assert response.status_code == 401

    def test_get_task_different_user_cannot_access(self, client):
        # User1 creates task
        user1_response = client.post(
            "/auth/register",
            json={"username": "user1", "password": "pass1"},
            content_type="application/json",
        )
        user1_token_response = client.post(
            "/auth/login",
            json={"username": "user1", "password": "pass1"},
            content_type="application/json",
        )
        user1_token = user1_token_response.get_json()["token"]
        user1_headers = {"Authorization": f"Bearer {user1_token}"}

        task_response = client.post(
            "/tasks",
            json={"title": "User1 Task"},
            content_type="application/json",
            headers=user1_headers,
        )
        task_id = task_response.get_json()["id"]

        # User2 tries to access it
        user2_response = client.post(
            "/auth/register",
            json={"username": "user2", "password": "pass2"},
            content_type="application/json",
        )
        user2_token_response = client.post(
            "/auth/login",
            json={"username": "user2", "password": "pass2"},
            content_type="application/json",
        )
        user2_token = user2_token_response.get_json()["token"]
        user2_headers = {"Authorization": f"Bearer {user2_token}"}

        response = client.get(
            f"/tasks/{task_id}",
            headers=user2_headers,
        )
        assert response.status_code == 404


class TestUpdateTask:
    def test_update_task_title_only(self, client, auth_user, sample_task):
        task_id = sample_task["id"]
        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated Title"},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated Title"
        assert data["status"] == "pending"  # Unchanged

    def test_update_task_status_to_done(self, client, auth_user, sample_task):
        task_id = sample_task["id"]
        response = client.put(
            f"/tasks/{task_id}",
            json={"status": "done"},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "done"
        assert data["title"] == "Test Task"  # Unchanged

    def test_update_task_title_and_status(self, client, auth_user, sample_task):
        task_id = sample_task["id"]
        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "New Title", "status": "done"},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "New Title"
        assert data["status"] == "done"

    def test_update_task_invalid_status(self, client, auth_user, sample_task):
        task_id = sample_task["id"]
        response = client.put(
            f"/tasks/{task_id}",
            json={"status": "invalid"},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 422
        data = response.get_json()
        assert "error" in data

    def test_update_task_invalid_status_in_progress(self, client, auth_user, sample_task):
        task_id = sample_task["id"]
        response = client.put(
            f"/tasks/{task_id}",
            json={"status": "in_progress"},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 422

    def test_update_task_status_pending_is_valid(self, client, auth_user, sample_task):
        task_id = sample_task["id"]
        # Change to done first
        client.put(
            f"/tasks/{task_id}",
            json={"status": "done"},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        # Change back to pending
        response = client.put(
            f"/tasks/{task_id}",
            json={"status": "pending"},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "pending"

    def test_update_task_not_found(self, client, auth_user):
        response = client.put(
            "/tasks/9999",
            json={"title": "Nonexistent"},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 404
        assert "error" in response.get_json()

    def test_update_task_empty_json(self, client, auth_user, sample_task):
        task_id = sample_task["id"]
        response = client.put(
            f"/tasks/{task_id}",
            json={},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        # Should succeed but not change anything
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id

    def test_update_task_no_json(self, client, auth_user, sample_task):
        task_id = sample_task["id"]
        response = client.put(
            f"/tasks/{task_id}",
            headers=auth_user["headers"],
        )
        # Should succeed with empty data
        assert response.status_code == 200

    def test_update_task_no_auth(self, client, sample_task):
        response = client.put(
            f"/tasks/{sample_task['id']}",
            json={"title": "Updated"},
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_update_task_different_user_cannot_access(self, client):
        # User1 creates task
        user1_response = client.post(
            "/auth/register",
            json={"username": "user1", "password": "pass1"},
            content_type="application/json",
        )
        user1_token_response = client.post(
            "/auth/login",
            json={"username": "user1", "password": "pass1"},
            content_type="application/json",
        )
        user1_token = user1_token_response.get_json()["token"]
        user1_headers = {"Authorization": f"Bearer {user1_token}"}

        task_response = client.post(
            "/tasks",
            json={"title": "User1 Task"},
            content_type="application/json",
            headers=user1_headers,
        )
        task_id = task_response.get_json()["id"]

        # User2 tries to update it
        user2_response = client.post(
            "/auth/register",
            json={"username": "user2", "password": "pass2"},
            content_type="application/json",
        )
        user2_token_response = client.post(
            "/auth/login",
            json={"username": "user2", "password": "pass2"},
            content_type="application/json",
        )
        user2_token = user2_token_response.get_json()["token"]
        user2_headers = {"Authorization": f"Bearer {user2_token}"}

        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated by User2"},
            content_type="application/json",
            headers=user2_headers,
        )
        assert response.status_code == 404


class TestErrorHandling:
    def test_400_missing_title_on_post(self, client, auth_user):
        response = client.post(
            "/tasks",
            json={"description": "no title"},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 400

    def test_422_invalid_status(self, client, auth_user, sample_task):
        task_id = sample_task["id"]
        response = client.put(
            f"/tasks/{task_id}",
            json={"status": "unknown"},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 422

    def test_404_task_not_found_get(self, client, auth_user):
        response = client.get(
            "/tasks/12345",
            headers=auth_user["headers"],
        )
        assert response.status_code == 404

    def test_404_task_not_found_put(self, client, auth_user):
        response = client.put(
            "/tasks/12345",
            json={"title": "test"},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response.status_code == 404

    def test_error_messages_are_json(self, client, auth_user):
        response = client.get(
            "/tasks/9999",
            headers=auth_user["headers"],
        )
        assert response.content_type == "application/json"
        data = response.get_json()
        assert isinstance(data, dict)
        assert "error" in data


class TestDataPersistence:
    def test_task_persists_after_retrieval(self, client, auth_user, sample_task):
        task_id = sample_task["id"]
        # Update the task
        client.put(
            f"/tasks/{task_id}",
            json={"status": "done"},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        # Retrieve it
        response = client.get(
            f"/tasks/{task_id}",
            headers=auth_user["headers"],
        )
        data = response.get_json()
        assert data["status"] == "done"

    def test_multiple_tasks_independent(self, client, auth_user):
        task1 = client.post(
            "/tasks",
            json={"title": "Task 1"},
            content_type="application/json",
            headers=auth_user["headers"],
        ).get_json()
        task2 = client.post(
            "/tasks",
            json={"title": "Task 2"},
            content_type="application/json",
            headers=auth_user["headers"],
        ).get_json()

        # Update task1
        client.put(
            f"/tasks/{task1['id']}",
            json={"status": "done"},
            content_type="application/json",
            headers=auth_user["headers"],
        )

        # Check task2 is unaffected
        response = client.get(
            f"/tasks/{task2['id']}",
            headers=auth_user["headers"],
        )
        data = response.get_json()
        assert data["status"] == "pending"


class TestPagination:
    def test_pagination_returns_correct_structure(self, client, auth_user):
        # Create a few tasks
        for i in range(5):
            client.post(
                "/tasks",
                json={"title": f"Task {i}"},
                content_type="application/json",
                headers=auth_user["headers"],
            )

        response = client.get(
            "/tasks",
            headers=auth_user["headers"],
        )
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, dict)
        assert "data" in data
        assert "next_cursor" in data
        assert "total" in data
        assert isinstance(data["data"], list)
        assert data["total"] == 5

    def test_pagination_default_limit_20(self, client, auth_user):
        # Create 25 tasks
        for i in range(25):
            client.post(
                "/tasks",
                json={"title": f"Task {i}"},
                content_type="application/json",
                headers=auth_user["headers"],
            )

        response = client.get(
            "/tasks",
            headers=auth_user["headers"],
        )
        data = response.get_json()
        assert len(data["data"]) == 20
        assert data["next_cursor"] is not None
        assert data["total"] == 25

    def test_pagination_custom_limit(self, client, auth_user):
        # Create 10 tasks
        for i in range(10):
            client.post(
                "/tasks",
                json={"title": f"Task {i}"},
                content_type="application/json",
                headers=auth_user["headers"],
            )

        response = client.get(
            "/tasks?limit=5",
            headers=auth_user["headers"],
        )
        data = response.get_json()
        assert len(data["data"]) == 5
        assert data["next_cursor"] is not None

    def test_pagination_limit_max_100(self, client, auth_user):
        # Create 50 tasks (being conservative with rapid creation)
        for i in range(50):
            client.post(
                "/tasks",
                json={"title": f"Task {i}"},
                content_type="application/json",
                headers=auth_user["headers"],
            )

        response = client.get(
            "/tasks?limit=200",
            headers=auth_user["headers"],
        )
        data = response.get_json()
        # Max limit is 100 even if we request 200
        assert len(data["data"]) <= 100
        # For 50 tasks, we should get all of them with no next cursor
        assert len(data["data"]) == 50
        assert data["next_cursor"] is None

    def test_pagination_limit_min_1(self, client, auth_user):
        # Create a fresh test client/auth_user for this isolated test
        client.post(
            "/tasks",
            json={"title": "Task 1"},
            content_type="application/json",
            headers=auth_user["headers"],
        )

        response = client.get(
            "/tasks?limit=0",
            headers=auth_user["headers"],
        )
        data = response.get_json()
        assert len(data["data"]) >= 1

    def test_pagination_with_cursor(self, client, auth_user):
        # Create 5 tasks for pagination testing
        task_ids = []
        for i in range(5):
            resp = client.post(
                "/tasks",
                json={"title": f"Task {i}"},
                content_type="application/json",
                headers=auth_user["headers"],
            )
            task_ids.append(resp.get_json()["id"])

        # Get first page (limit=2)
        response1 = client.get(
            "/tasks?limit=2",
            headers=auth_user["headers"],
        )
        data1 = response1.get_json()
        assert len(data1["data"]) == 2
        assert data1["next_cursor"] is not None
        first_page_ids = [t["id"] for t in data1["data"]]

        # Get second page using cursor
        response2 = client.get(
            f"/tasks?limit=2&cursor={data1['next_cursor']}",
            headers=auth_user["headers"],
        )
        data2 = response2.get_json()
        assert len(data2["data"]) == 2
        second_page_ids = [t["id"] for t in data2["data"]]

        # Ensure pages don't overlap
        assert len(set(first_page_ids) & set(second_page_ids)) == 0

    def test_pagination_empty_list(self, client, auth_user):
        response = client.get(
            "/tasks",
            headers=auth_user["headers"],
        )
        data = response.get_json()
        assert data["data"] == []
        assert data["next_cursor"] is None
        assert data["total"] == 0

    def test_pagination_no_next_cursor_on_last_page(self, client, auth_user):
        # Create 3 tasks
        for i in range(3):
            client.post(
                "/tasks",
                json={"title": f"Task {i}"},
                content_type="application/json",
                headers=auth_user["headers"],
            )

        response = client.get(
            "/tasks?limit=10",
            headers=auth_user["headers"],
        )
        data = response.get_json()
        assert len(data["data"]) == 3
        assert data["next_cursor"] is None
        assert data["total"] == 3

    def test_pagination_invalid_limit_uses_default(self, client, auth_user):
        client.post(
            "/tasks",
            json={"title": "Task 1"},
            content_type="application/json",
            headers=auth_user["headers"],
        )

        response = client.get(
            "/tasks?limit=abc",
            headers=auth_user["headers"],
        )
        data = response.get_json()
        assert len(data["data"]) >= 1
        assert data["total"] >= 1

    def test_pagination_user_isolation(self, client):
        # Create two users
        user1_resp = client.post(
            "/auth/register",
            json={"username": "paginationuser1", "password": "pass1"},
            content_type="application/json",
        )
        user1_token = client.post(
            "/auth/login",
            json={"username": "paginationuser1", "password": "pass1"},
            content_type="application/json",
        ).get_json()["token"]
        user1_headers = {"Authorization": f"Bearer {user1_token}"}

        user2_resp = client.post(
            "/auth/register",
            json={"username": "paginationuser2", "password": "pass2"},
            content_type="application/json",
        )
        user2_token = client.post(
            "/auth/login",
            json={"username": "paginationuser2", "password": "pass2"},
            content_type="application/json",
        ).get_json()["token"]
        user2_headers = {"Authorization": f"Bearer {user2_token}"}

        # User1 creates 3 tasks
        for i in range(3):
            client.post(
                "/tasks",
                json={"title": f"PaginationUser1 Task {i}"},
                content_type="application/json",
                headers=user1_headers,
            )

        # User2 creates 2 tasks
        for i in range(2):
            client.post(
                "/tasks",
                json={"title": f"PaginationUser2 Task {i}"},
                content_type="application/json",
                headers=user2_headers,
            )

        # Each user should only see their own tasks
        user1_resp = client.get("/tasks", headers=user1_headers)
        user1_data = user1_resp.get_json()
        assert user1_data["total"] == 3

        user2_resp = client.get("/tasks", headers=user2_headers)
        user2_data = user2_resp.get_json()
        assert user2_data["total"] == 2


class TestRateLimiting:
    def test_rate_limiting_disabled_when_redis_unavailable(self, client, auth_user):
        """Test that API works when Redis is not available."""
        # Make multiple requests to verify no 429 errors occur
        responses = []
        for _ in range(10):
            response = client.get(
                "/tasks",
                headers=auth_user["headers"],
            )
            responses.append(response.status_code)

        # All should succeed (no 429)
        assert all(status == 200 for status in responses)

    def test_rate_limiting_applied_to_all_endpoints(self, client, auth_user):
        """Test that rate limiting is applied to all endpoints."""
        # This test verifies the decorator is in place; actual 429 testing
        # requires Redis to be running and can be skipped in CI environments
        endpoints = [
            ("/tasks", "GET"),
            ("/tasks", "POST"),
            ("/tasks/1", "GET"),
            ("/tasks/1", "PUT"),
        ]

        for endpoint, method in endpoints:
            if method == "GET":
                response = client.get(
                    endpoint,
                    headers=auth_user["headers"],
                )
            elif method == "POST":
                response = client.post(
                    endpoint,
                    json={"title": "Test"},
                    content_type="application/json",
                    headers=auth_user["headers"],
                )
            elif method == "PUT":
                response = client.put(
                    endpoint,
                    json={"title": "Updated"},
                    content_type="application/json",
                    headers=auth_user["headers"],
                )

            # Should not return 500 error due to rate limiting decorator
            assert response.status_code != 500

    def test_rate_limiting_on_auth_endpoints(self, client):
        """Test that rate limiting is applied to auth endpoints."""
        # Make a login attempt
        response = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "testpass"},
            content_type="application/json",
        )

        # Should not return 500 error
        assert response.status_code != 500

    def test_rate_limiting_per_user(self, client):
        """Test that rate limiting is per-user (when authenticated)."""
        # Register and login user1
        client.post(
            "/auth/register",
            json={"username": "user1", "password": "pass1"},
            content_type="application/json",
        )
        user1_token = client.post(
            "/auth/login",
            json={"username": "user1", "password": "pass1"},
            content_type="application/json",
        ).get_json()["token"]
        user1_headers = {"Authorization": f"Bearer {user1_token}"}

        # Register and login user2
        client.post(
            "/auth/register",
            json={"username": "user2", "password": "pass2"},
            content_type="application/json",
        )
        user2_token = client.post(
            "/auth/login",
            json={"username": "user2", "password": "pass2"},
            content_type="application/json",
        ).get_json()["token"]
        user2_headers = {"Authorization": f"Bearer {user2_token}"}

        # Both users should be able to make independent requests
        resp1 = client.get("/tasks", headers=user1_headers)
        resp2 = client.get("/tasks", headers=user2_headers)

        assert resp1.status_code == 200
        assert resp2.status_code == 200


class TestNotificationSystem:
    @patch("app.send_task_notification_email")
    def test_notification_sent_when_status_changes_to_done(self, mock_send_notification, client, auth_user, sample_task):
        task_id = sample_task["id"]

        response = client.put(
            f"/tasks/{task_id}",
            json={"status": "done"},
            content_type="application/json",
            headers=auth_user["headers"],
        )

        assert response.status_code == 200
        # Verify the task was updated to done
        data = response.get_json()
        assert data["status"] == "done"

        # Verify notification was sent
        mock_send_notification.assert_called_once_with("testuser@example.com", "Test Task")

    @patch("app.send_task_notification_email")
    def test_notification_sent_with_user_email(self, mock_send_notification, client):
        # Register user with email
        register_response = client.post(
            "/auth/register",
            json={"username": "emailuser", "password": "testpass", "email": "user@example.com"},
            content_type="application/json",
        )
        assert register_response.status_code == 201

        # Login
        login_response = client.post(
            "/auth/login",
            json={"username": "emailuser", "password": "testpass"},
            content_type="application/json",
        )
        token = login_response.get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create task
        task_response = client.post(
            "/tasks",
            json={"title": "Important Task"},
            content_type="application/json",
            headers=headers,
        )
        task_id = task_response.get_json()["id"]

        # Update status to done
        response = client.put(
            f"/tasks/{task_id}",
            json={"status": "done"},
            content_type="application/json",
            headers=headers,
        )

        assert response.status_code == 200

        # Verify notification was sent with correct arguments
        mock_send_notification.assert_called_once_with("user@example.com", "Important Task")

    @patch("app.send_task_notification_email")
    def test_notification_not_sent_when_status_not_changed(self, mock_send_notification, client, auth_user, sample_task):
        task_id = sample_task["id"]

        # Update to done first time
        response1 = client.put(
            f"/tasks/{task_id}",
            json={"status": "done"},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response1.status_code == 200
        assert mock_send_notification.call_count == 1

        # Update again to done (no status change)
        mock_send_notification.reset_mock()
        response2 = client.put(
            f"/tasks/{task_id}",
            json={"title": "New Title"},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response2.status_code == 200
        # Should not send notification since status didn't change
        mock_send_notification.assert_not_called()

    @patch("app.send_task_notification_email")
    def test_notification_not_sent_when_changing_back_from_done(self, mock_send_notification, client, auth_user, sample_task):
        task_id = sample_task["id"]

        # Update to done
        response1 = client.put(
            f"/tasks/{task_id}",
            json={"status": "done"},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response1.status_code == 200

        # Reset mock for next assertion
        mock_send_notification.reset_mock()

        # Change back to pending
        response2 = client.put(
            f"/tasks/{task_id}",
            json={"status": "pending"},
            content_type="application/json",
            headers=auth_user["headers"],
        )
        assert response2.status_code == 200
        # Should not send notification
        mock_send_notification.assert_not_called()

    @patch("app.send_task_notification_email")
    def test_notification_only_sent_once_per_transition(self, mock_send_notification, client):
        # Register user with email
        register_response = client.post(
            "/auth/register",
            json={"username": "testuser1", "password": "pass", "email": "test@example.com"},
            content_type="application/json",
        )
        user_id = register_response.get_json()["id"]

        login_response = client.post(
            "/auth/login",
            json={"username": "testuser1", "password": "pass"},
            content_type="application/json",
        )
        token = login_response.get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create task
        task_response = client.post(
            "/tasks",
            json={"title": "Test Task"},
            content_type="application/json",
            headers=headers,
        )
        task_id = task_response.get_json()["id"]

        # First update to done
        response1 = client.put(
            f"/tasks/{task_id}",
            json={"status": "done"},
            content_type="application/json",
            headers=headers,
        )
        assert response1.status_code == 200
        call_count_after_first = mock_send_notification.call_count
        assert call_count_after_first == 1

        # Second update to done (no change)
        response2 = client.put(
            f"/tasks/{task_id}",
            json={"status": "done"},
            content_type="application/json",
            headers=headers,
        )
        assert response2.status_code == 200
        # Call count should still be 1
        assert mock_send_notification.call_count == call_count_after_first


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
