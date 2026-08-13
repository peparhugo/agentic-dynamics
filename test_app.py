"""
pytest tests for the task management API.
"""

import pytest
import json
import os
import tempfile
import shutil
from app import app
import app as app_module


@pytest.fixture
def client(monkeypatch):
    """Create a test client with a temporary data directory."""
    temp_dir = tempfile.mkdtemp()
    temp_tasks_file = os.path.join(temp_dir, "tasks.json")

    # Patch the module-level variables
    monkeypatch.setattr(app_module, "DATA_DIR", temp_dir)
    monkeypatch.setattr(app_module, "TASKS_FILE", temp_tasks_file)

    with app.test_client() as client:
        yield client

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_create_task_success(client):
    """Test creating a task with valid data."""
    response = client.post("/tasks", json={"title": "Test Task"})
    assert response.status_code == 201
    data = response.json
    assert data["id"] == 1
    assert data["title"] == "Test Task"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_create_task_missing_title(client):
    """Test creating a task without a title returns 400."""
    response = client.post("/tasks", json={})
    assert response.status_code == 400
    assert "error" in response.json
    assert "title" in response.json["error"]


def test_create_task_empty_title(client):
    """Test creating a task with empty title returns 400."""
    response = client.post("/tasks", json={"title": ""})
    assert response.status_code == 400
    assert "error" in response.json


def test_create_task_whitespace_title(client):
    """Test creating a task with whitespace-only title returns 400."""
    response = client.post("/tasks", json={"title": "   "})
    assert response.status_code == 400
    assert "error" in response.json


def test_create_task_no_json(client):
    """Test creating a task without JSON body returns 400."""
    response = client.post("/tasks", json={"other": "field"})
    assert response.status_code == 400


def test_create_multiple_tasks(client):
    """Test creating multiple tasks with incrementing IDs."""
    response1 = client.post("/tasks", json={"title": "First Task"})
    response2 = client.post("/tasks", json={"title": "Second Task"})

    assert response1.status_code == 201
    assert response2.status_code == 201
    assert response1.json["id"] == 1
    assert response2.json["id"] == 2


def test_list_tasks_empty(client):
    """Test listing tasks when none exist."""
    response = client.get("/tasks")
    assert response.status_code == 200
    assert response.json == []


def test_list_tasks_ordered_by_created_at_desc(client):
    """Test that tasks are returned ordered by created_at descending."""
    client.post("/tasks", json={"title": "First"})
    client.post("/tasks", json={"title": "Second"})
    client.post("/tasks", json={"title": "Third"})

    response = client.get("/tasks")
    assert response.status_code == 200
    tasks = response.json
    assert len(tasks) == 3
    # Most recent task first
    assert tasks[0]["title"] == "Third"
    assert tasks[1]["title"] == "Second"
    assert tasks[2]["title"] == "First"


def test_get_task_success(client):
    """Test getting a single task by ID."""
    create_response = client.post("/tasks", json={"title": "Test Task"})
    task_id = create_response.json["id"]

    response = client.get(f"/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json["id"] == task_id
    assert response.json["title"] == "Test Task"


def test_get_task_not_found(client):
    """Test getting a non-existent task returns 404."""
    response = client.get("/tasks/999")
    assert response.status_code == 404
    assert "error" in response.json
    assert "not found" in response.json["error"]


def test_update_task_title(client):
    """Test updating a task's title."""
    create_response = client.post("/tasks", json={"title": "Original"})
    task_id = create_response.json["id"]

    response = client.put(f"/tasks/{task_id}", json={"title": "Updated"})
    assert response.status_code == 200
    assert response.json["title"] == "Updated"
    assert response.json["status"] == "pending"


def test_update_task_status(client):
    """Test updating a task's status."""
    create_response = client.post("/tasks", json={"title": "Test"})
    task_id = create_response.json["id"]

    response = client.put(f"/tasks/{task_id}", json={"status": "completed"})
    assert response.status_code == 200
    assert response.json["status"] == "completed"
    assert response.json["title"] == "Test"


def test_update_task_both_fields(client):
    """Test updating both title and status."""
    create_response = client.post("/tasks", json={"title": "Original"})
    task_id = create_response.json["id"]

    response = client.put(f"/tasks/{task_id}", json={
        "title": "New Title",
        "status": "in_progress"
    })
    assert response.status_code == 200
    assert response.json["title"] == "New Title"
    assert response.json["status"] == "in_progress"


def test_update_task_empty_title(client):
    """Test updating with empty title returns 400."""
    create_response = client.post("/tasks", json={"title": "Original"})
    task_id = create_response.json["id"]

    response = client.put(f"/tasks/{task_id}", json={"title": ""})
    assert response.status_code == 400
    assert "error" in response.json


def test_update_task_not_found(client):
    """Test updating a non-existent task returns 404."""
    response = client.put("/tasks/999", json={"title": "New"})
    assert response.status_code == 404
    assert "error" in response.json


def test_update_task_no_changes(client):
    """Test updating a task with no fields just returns the task."""
    create_response = client.post("/tasks", json={"title": "Test"})
    task_id = create_response.json["id"]
    original_title = create_response.json["title"]

    response = client.put(f"/tasks/{task_id}", json={})
    assert response.status_code == 200
    assert response.json["title"] == original_title


def test_persistence_across_requests(client):
    """Test that data persists across multiple requests."""
    response1 = client.post("/tasks", json={"title": "Persistent Task"})
    task_id = response1.json["id"]

    response2 = client.get(f"/tasks/{task_id}")
    assert response2.status_code == 200
    assert response2.json["title"] == "Persistent Task"

    response3 = client.get("/tasks")
    assert len(response3.json) == 1


def test_task_created_at_format(client):
    """Test that created_at is in ISO format."""
    response = client.post("/tasks", json={"title": "Test"})
    created_at = response.json["created_at"]
    # ISO format includes 'T' and microseconds or 'Z'
    assert "T" in created_at or "Z" in created_at


def test_create_task_with_extra_fields(client):
    """Test that extra fields in request are ignored."""
    response = client.post("/tasks", json={
        "title": "Test",
        "extra_field": "ignored",
        "another": "also ignored"
    })
    assert response.status_code == 201
    # Response should only have expected fields
    assert "extra_field" not in response.json
    assert "another" not in response.json
