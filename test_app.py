import pytest
import app as app_module
from datetime import datetime, timezone
import os
import json


@pytest.fixture
def client():
    app_module.DATABASE = "test_tasks.db"
    app_module.init_db()
    yield app_module.app.test_client()
    if os.path.exists("test_tasks.db"):
        os.remove("test_tasks.db")


class TestCreateTask:
    def test_create_task_success(self, client):
        response = client.post("/tasks", json={"title": "My Task"})
        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "My Task"
        assert data["status"] == "pending"
        assert data["id"] == 1
        assert "created_at" in data

    def test_create_task_missing_title(self, client):
        response = client.post("/tasks", json={})
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_create_task_empty_title(self, client):
        response = client.post("/tasks", json={"title": ""})
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_create_task_whitespace_title(self, client):
        response = client.post("/tasks", json={"title": "   "})
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_create_task_default_status_pending(self, client):
        response = client.post("/tasks", json={"title": "Task"})
        assert response.status_code == 201
        assert response.get_json()["status"] == "pending"


class TestListTasks:
    def test_list_tasks_empty(self, client):
        response = client.get("/tasks")
        assert response.status_code == 200
        assert response.get_json() == []

    def test_list_tasks_multiple(self, client):
        client.post("/tasks", json={"title": "Task 1"})
        client.post("/tasks", json={"title": "Task 2"})
        client.post("/tasks", json={"title": "Task 3"})
        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 3
        assert data[0]["title"] == "Task 3"
        assert data[1]["title"] == "Task 2"
        assert data[2]["title"] == "Task 1"


class TestGetTask:
    def test_get_task_success(self, client):
        client.post("/tasks", json={"title": "My Task"})
        response = client.get("/tasks/1")
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == 1
        assert data["title"] == "My Task"
        assert data["status"] == "pending"

    def test_get_task_not_found(self, client):
        response = client.get("/tasks/999")
        assert response.status_code == 404
        assert response.get_json()["error"] == "task not found"


class TestUpdateTask:
    def test_update_title(self, client):
        client.post("/tasks", json={"title": "Original"})
        response = client.put("/tasks/1", json={"title": "Updated"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated"
        assert data["status"] == "pending"

    def test_update_status(self, client):
        client.post("/tasks", json={"title": "Task"})
        response = client.put("/tasks/1", json={"status": "completed"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Task"
        assert data["status"] == "completed"

    def test_update_both(self, client):
        client.post("/tasks", json={"title": "Task"})
        response = client.put(
            "/tasks/1", json={"title": "Renamed", "status": "in_progress"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Renamed"
        assert data["status"] == "in_progress"

    def test_update_not_found(self, client):
        response = client.put("/tasks/999", json={"title": "Nope"})
        assert response.status_code == 404
        assert response.get_json()["error"] == "task not found"

    def test_update_empty_title(self, client):
        client.post("/tasks", json={"title": "Task"})
        response = client.put("/tasks/1", json={"title": ""})
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_update_whitespace_title(self, client):
        client.post("/tasks", json={"title": "Task"})
        response = client.put("/tasks/1", json={"title": "   "})
        assert response.status_code == 400
        assert response.get_json()["error"] == "title is required"

    def test_update_no_fields(self, client):
        client.post("/tasks", json={"title": "Task"})
        response = client.put("/tasks/1", json={})
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Task"
        assert data["status"] == "pending"


class TestErrorResponsesAreJSON:
    def test_posts_non_json_body(self, client):
        response = client.post(
            "/tasks",
            data="not json",
            content_type="text/plain",
        )
        assert response.status_code == 400
        assert response.is_json
        assert "error" in response.get_json()

    def test_404_is_json(self, client):
        response = client.get("/tasks/999")
        assert response.status_code == 404
        assert response.is_json
        assert "error" in response.get_json()
