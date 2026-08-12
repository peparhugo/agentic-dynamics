"""
Test suite for the Flask Task Management API (app.py).

Covers:
 - POST /tasks (success + missing title -> 400)
 - GET /tasks (list, ordered by created_at desc)
 - GET /tasks/{id} (found + 404 when missing)
 - PUT /tasks/{id} (update title and/or status + 404 when missing)
"""

import json
import os
import sys

import pytest

# Make sure the project root (parent of tests/) is importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Provide a Flask test client backed by a fresh SQLite DB file per test."""
    db_path = tmp_path / "test_tasks.db"
    monkeypatch.setattr(app_module, "DATABASE", str(db_path))
    app_module.init_db()

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client


def _create_task(client, title="Buy milk"):
    return client.post(
        "/tasks",
        data=json.dumps({"title": title}),
        content_type="application/json",
    )


# ── POST /tasks ──────────────────────────────────────────────────


def test_create_task_success(client):
    resp = _create_task(client, "Write report")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["title"] == "Write report"
    assert body["status"] == "pending"
    assert isinstance(body["id"], int)
    assert "created_at" in body


def test_create_task_missing_title_returns_400(client):
    resp = client.post(
        "/tasks", data=json.dumps({}), content_type="application/json"
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert "error" in body


def test_create_task_blank_title_returns_400(client):
    resp = client.post(
        "/tasks",
        data=json.dumps({"title": "   "}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert "error" in body


def test_create_task_no_json_body_returns_400(client):
    resp = client.post("/tasks")
    assert resp.status_code == 400
    body = resp.get_json()
    assert "error" in body


# ── GET /tasks ───────────────────────────────────────────────────


def test_list_tasks_empty(client):
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_tasks_ordered_by_created_at_desc(client):
    _create_task(client, "First task")
    _create_task(client, "Second task")
    _create_task(client, "Third task")

    resp = client.get("/tasks")
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["Third task", "Second task", "First task"]


# ── GET /tasks/{id} ──────────────────────────────────────────────


def test_get_single_task_success(client):
    created = _create_task(client, "Read book").get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["id"] == created["id"]
    assert body["title"] == "Read book"


def test_get_single_task_not_found(client):
    resp = client.get("/tasks/9999")
    assert resp.status_code == 404
    body = resp.get_json()
    assert "error" in body


# ── PUT /tasks/{id} ──────────────────────────────────────────────


def test_update_task_title_only(client):
    created = _create_task(client, "Old title").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"title": "New title"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "New title"
    assert body["status"] == "pending"


def test_update_task_status_only(client):
    created = _create_task(client, "Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "done"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "Task"
    assert body["status"] == "done"


def test_update_task_title_and_status(client):
    created = _create_task(client, "Task").get_json()
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
    body = resp.get_json()
    assert "error" in body


def test_update_task_persisted(client):
    created = _create_task(client, "Persisted task").get_json()
    client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "done"}),
        content_type="application/json",
    )
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.get_json()["status"] == "done"
