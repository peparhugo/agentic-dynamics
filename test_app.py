import json
import os
import time

import pytest

from app import app, init_db


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["DATABASE"] = "test_tasks.db"
    import app as app_module

    app_module.DATABASE = "test_tasks.db"

    with app.test_client() as client:
        init_db()
        yield client

    if os.path.exists("test_tasks.db"):
        os.remove("test_tasks.db")


def test_create_task(client):
    resp = client.post(
        "/tasks", data=json.dumps({"title": "Test task"}), content_type="application/json"
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Test task"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_create_task_missing_title(client):
    resp = client.post(
        "/tasks", data=json.dumps({}), content_type="application/json"
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_no_body(client):
    resp = client.post("/tasks", content_type="application/json")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks(client):
    client.post(
        "/tasks", data=json.dumps({"title": "Task 1"}), content_type="application/json"
    )
    time.sleep(0.01)
    client.post(
        "/tasks", data=json.dumps({"title": "Task 2"}), content_type="application/json"
    )

    resp = client.get("/tasks")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2
    assert data[0]["title"] == "Task 2"
    assert data[1]["title"] == "Task 1"


def test_list_tasks_empty(client):
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_get_task(client):
    client.post(
        "/tasks", data=json.dumps({"title": "Test task"}), content_type="application/json"
    )
    resp = client.get("/tasks/1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Test task"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_get_task_not_found(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client):
    client.post(
        "/tasks", data=json.dumps({"title": "Old title"}), content_type="application/json"
    )
    resp = client.put(
        "/tasks/1",
        data=json.dumps({"title": "New title"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status(client):
    client.post(
        "/tasks", data=json.dumps({"title": "Task"}), content_type="application/json"
    )
    resp = client.put(
        "/tasks/1",
        data=json.dumps({"status": "done"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Task"
    assert data["status"] == "done"


def test_update_task_both(client):
    client.post(
        "/tasks", data=json.dumps({"title": "Old"}), content_type="application/json"
    )
    resp = client.put(
        "/tasks/1",
        data=json.dumps({"title": "New", "status": "done"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New"
    assert data["status"] == "done"


def test_update_task_not_found(client):
    resp = client.put(
        "/tasks/999",
        data=json.dumps({"title": "New"}),
        content_type="application/json",
    )
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_created_at_is_iso_string(client):
    resp = client.post(
        "/tasks", data=json.dumps({"title": "Time test"}), content_type="application/json"
    )
    data = resp.get_json()
    assert isinstance(data["created_at"], str)
    assert "T" in data["created_at"]
