"""
Tests for the Flask Task Management API.
"""

import json
import time

import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / "test_tasks.db"
    flask_app = create_app(database=str(db_path))
    flask_app.config.update(TESTING=True)
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def create(client, title="Buy milk"):
    return client.post(
        "/tasks",
        data=json.dumps({"title": title}),
        content_type="application/json",
    )


# ── POST /tasks ──────────────────────────────────────────────

def test_create_task_success(client):
    resp = create(client, "Write report")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["title"] == "Write report"
    assert body["status"] == "pending"
    assert isinstance(body["id"], int)
    assert "created_at" in body


def test_create_task_missing_title_returns_400(client):
    resp = client.post("/tasks", data=json.dumps({}), content_type="application/json")
    assert resp.status_code == 400
    body = resp.get_json()
    assert "error" in body


def test_create_task_empty_title_returns_400(client):
    resp = create(client, "   ")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_no_body_returns_400(client):
    resp = client.post("/tasks")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_non_string_title_returns_400(client):
    resp = client.post(
        "/tasks", data=json.dumps({"title": 123}), content_type="application/json"
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_strips_whitespace(client):
    resp = create(client, "  Padded title  ")
    assert resp.status_code == 201
    assert resp.get_json()["title"] == "Padded title"


# ── GET /tasks ───────────────────────────────────────────────

def test_list_tasks_empty(client):
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_tasks_ordered_desc_by_created_at(client):
    create(client, "First")
    time.sleep(0.01)
    create(client, "Second")
    time.sleep(0.01)
    create(client, "Third")

    resp = client.get("/tasks")
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["Third", "Second", "First"]


def test_list_tasks_returns_all_fields(client):
    create(client, "Task A")
    resp = client.get("/tasks")
    task = resp.get_json()[0]
    assert set(task.keys()) == {"id", "title", "status", "created_at"}


# ── GET /tasks/{id} ──────────────────────────────────────────

def test_get_single_task_success(client):
    created = create(client, "Detail task").get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["id"] == created["id"]
    assert body["title"] == "Detail task"


def test_get_single_task_not_found(client):
    resp = client.get("/tasks/9999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


# ── PUT /tasks/{id} ──────────────────────────────────────────

def test_update_task_title(client):
    created = create(client, "Old title").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"title": "New title"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "New title"
    assert body["status"] == "pending"


def test_update_task_status(client):
    created = create(client, "Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "done"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "done"
    assert body["title"] == "Task"


def test_update_task_title_and_status(client):
    created = create(client, "Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"title": "Updated", "status": "in_progress"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "Updated"
    assert body["status"] == "in_progress"


def test_update_task_not_found(client):
    resp = client.put(
        "/tasks/9999",
        data=json.dumps({"title": "Nope"}),
        content_type="application/json",
    )
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_no_fields_returns_400(client):
    created = create(client, "Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_update_task_empty_title_returns_400(client):
    created = create(client, "Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"title": "   "}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_update_task_persists(client):
    created = create(client, "Task").get_json()
    client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "done"}),
        content_type="application/json",
    )
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.get_json()["status"] == "done"


# ── Misc ─────────────────────────────────────────────────────

def test_schema_initialized_on_startup(tmp_path):
    db_path = tmp_path / "fresh.db"
    assert not db_path.exists()
    app = create_app(database=str(db_path))
    assert db_path.exists()

    client = app.test_client()
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_404_for_unknown_route(client):
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404
    body = resp.get_json()
    assert "error" in body
