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
def sample_task(client):
    """Create a sample task for testing."""
    response = client.post(
        "/tasks",
        json={"title": "Test Task"},
        content_type="application/json",
    )
    return response.get_json()


class TestCreateTask:
    def test_create_task_success(self, client):
        response = client.post(
            "/tasks",
            json={"title": "Buy groceries"},
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Buy groceries"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data

    def test_create_task_missing_title(self, client):
        response = client.post(
            "/tasks",
            json={},
            content_type="application/json",
        )
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_create_task_empty_title(self, client):
        response = client.post(
            "/tasks",
            json={"title": "   "},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_create_task_no_json(self, client):
        response = client.post("/tasks")
        assert response.status_code == 400

    def test_created_at_is_iso8601(self, client):
        response = client.post(
            "/tasks",
            json={"title": "Check ISO format"},
            content_type="application/json",
        )
        data = response.get_json()
        # Should be ISO-8601 format
        try:
            datetime.fromisoformat(data["created_at"])
        except ValueError:
            pytest.fail(f"created_at not in ISO-8601 format: {data['created_at']}")


class TestListTasks:
    def test_list_empty(self, client):
        response = client.get("/tasks")
        assert response.status_code == 200
        assert response.get_json() == []

    def test_list_single_task(self, client, sample_task):
        response = client.get("/tasks")
        assert response.status_code == 200
        tasks = response.get_json()
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Test Task"

    def test_list_multiple_tasks_ordered_by_created_at_desc(self, client):
        # Create tasks with slight delays to ensure different timestamps
        task1 = client.post(
            "/tasks",
            json={"title": "First"},
            content_type="application/json",
        ).get_json()

        task2 = client.post(
            "/tasks",
            json={"title": "Second"},
            content_type="application/json",
        ).get_json()

        task3 = client.post(
            "/tasks",
            json={"title": "Third"},
            content_type="application/json",
        ).get_json()

        response = client.get("/tasks")
        tasks = response.get_json()
        assert len(tasks) == 3
        # Should be ordered by created_at DESC (newest first)
        assert tasks[0]["id"] == task3["id"]
        assert tasks[1]["id"] == task2["id"]
        assert tasks[2]["id"] == task1["id"]


class TestGetSingleTask:
    def test_get_task_success(self, client, sample_task):
        task_id = sample_task["id"]
        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id
        assert data["title"] == "Test Task"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client):
        response = client.get("/tasks/9999")
        assert response.status_code == 404
        assert "error" in response.get_json()

    def test_get_task_zero_id(self, client):
        response = client.get("/tasks/0")
        assert response.status_code == 404


class TestUpdateTask:
    def test_update_task_title_only(self, client, sample_task):
        task_id = sample_task["id"]
        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated Title"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated Title"
        assert data["status"] == "pending"  # Unchanged

    def test_update_task_status_to_done(self, client, sample_task):
        task_id = sample_task["id"]
        response = client.put(
            f"/tasks/{task_id}",
            json={"status": "done"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "done"
        assert data["title"] == "Test Task"  # Unchanged

    def test_update_task_title_and_status(self, client, sample_task):
        task_id = sample_task["id"]
        response = client.put(
            f"/tasks/{task_id}",
            json={"title": "New Title", "status": "done"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "New Title"
        assert data["status"] == "done"

    def test_update_task_invalid_status(self, client, sample_task):
        task_id = sample_task["id"]
        response = client.put(
            f"/tasks/{task_id}",
            json={"status": "invalid"},
            content_type="application/json",
        )
        assert response.status_code == 422
        data = response.get_json()
        assert "error" in data

    def test_update_task_invalid_status_in_progress(self, client, sample_task):
        task_id = sample_task["id"]
        response = client.put(
            f"/tasks/{task_id}",
            json={"status": "in_progress"},
            content_type="application/json",
        )
        assert response.status_code == 422

    def test_update_task_status_pending_is_valid(self, client, sample_task):
        task_id = sample_task["id"]
        # Change to done first
        client.put(
            f"/tasks/{task_id}",
            json={"status": "done"},
            content_type="application/json",
        )
        # Change back to pending
        response = client.put(
            f"/tasks/{task_id}",
            json={"status": "pending"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "pending"

    def test_update_task_not_found(self, client):
        response = client.put(
            "/tasks/9999",
            json={"title": "Nonexistent"},
            content_type="application/json",
        )
        assert response.status_code == 404
        assert "error" in response.get_json()

    def test_update_task_empty_json(self, client, sample_task):
        task_id = sample_task["id"]
        response = client.put(
            f"/tasks/{task_id}",
            json={},
            content_type="application/json",
        )
        # Should succeed but not change anything
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == task_id

    def test_update_task_no_json(self, client, sample_task):
        task_id = sample_task["id"]
        response = client.put(f"/tasks/{task_id}")
        # Should succeed with empty data
        assert response.status_code == 200


class TestErrorHandling:
    def test_400_missing_title_on_post(self, client):
        response = client.post(
            "/tasks",
            json={"description": "no title"},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_422_invalid_status(self, client, sample_task):
        task_id = sample_task["id"]
        response = client.put(
            f"/tasks/{task_id}",
            json={"status": "unknown"},
            content_type="application/json",
        )
        assert response.status_code == 422

    def test_404_task_not_found_get(self, client):
        response = client.get("/tasks/12345")
        assert response.status_code == 404

    def test_404_task_not_found_put(self, client):
        response = client.put(
            "/tasks/12345",
            json={"title": "test"},
            content_type="application/json",
        )
        assert response.status_code == 404

    def test_error_messages_are_json(self, client):
        response = client.get("/tasks/9999")
        assert response.content_type == "application/json"
        data = response.get_json()
        assert isinstance(data, dict)
        assert "error" in data


class TestDataPersistence:
    def test_task_persists_after_retrieval(self, client, sample_task):
        task_id = sample_task["id"]
        # Update the task
        client.put(
            f"/tasks/{task_id}",
            json={"status": "done"},
            content_type="application/json",
        )
        # Retrieve it
        response = client.get(f"/tasks/{task_id}")
        data = response.get_json()
        assert data["status"] == "done"

    def test_multiple_tasks_independent(self, client):
        task1 = client.post(
            "/tasks",
            json={"title": "Task 1"},
            content_type="application/json",
        ).get_json()
        task2 = client.post(
            "/tasks",
            json={"title": "Task 2"},
            content_type="application/json",
        ).get_json()

        # Update task1
        client.put(
            f"/tasks/{task1['id']}",
            json={"status": "done"},
            content_type="application/json",
        )

        # Check task2 is unaffected
        response = client.get(f"/tasks/{task2['id']}")
        data = response.get_json()
        assert data["status"] == "pending"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
