import pytest
import json
import os
import sqlite3
import tempfile
from datetime import datetime
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
        json={"username": "testuser", "password": "testpass"},
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
        assert response.get_json() == []

    def test_list_single_task(self, client, auth_user, sample_task):
        response = client.get(
            "/tasks",
            headers=auth_user["headers"],
        )
        assert response.status_code == 200
        tasks = response.get_json()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Test Task"

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
        tasks = response.get_json()
        assert len(tasks) == 3
        # Should be ordered by created_at DESC (newest first)
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
        user1_tasks = user1_tasks_response.get_json()
        assert len(user1_tasks) == 1
        assert user1_tasks[0]["title"] == "User1 Task"
        assert user1_tasks[0]["owner_id"] == user1_id

        # User2 should only see their own task
        user2_tasks_response = client.get("/tasks", headers=user2_headers)
        user2_tasks = user2_tasks_response.get_json()
        assert len(user2_tasks) == 1
        assert user2_tasks[0]["title"] == "User2 Task"
        assert user2_tasks[0]["owner_id"] == user2_id


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
