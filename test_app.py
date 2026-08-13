import os
import time

import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "test_todos.db"
    app_module.DATABASE = str(db_path)
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client


def _create(client, title="Buy milk"):
    return client.post("/tasks", json={"title": title})


# ── POST /tasks ──────────────────────────────────────────────


def test_create_task_returns_201_and_task(client):
    resp = _create(client, "Write report")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["title"] == "Write report"
    assert body["status"] == "pending"
    assert isinstance(body["id"], int)
    assert "created_at" in body


def test_create_task_persists(client):
    _create(client, "Persisted task")
    resp = client.get("/tasks")
    titles = [t["title"] for t in resp.get_json()]
    assert "Persisted task" in titles


def test_create_task_missing_title_returns_400(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    body = resp.get_json()
    assert "error" in body


def test_create_task_blank_title_returns_400(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_no_json_body_returns_400(client):
    resp = client.post("/tasks")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


# ── GET /tasks ───────────────────────────────────────────────


def test_list_tasks_empty(client):
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_tasks_ordered_desc_by_created_at(client):
    _create(client, "first")
    time.sleep(0.01)
    _create(client, "second")
    time.sleep(0.01)
    _create(client, "third")

    resp = client.get("/tasks")
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["third", "second", "first"]


# ── GET /tasks/{id} ──────────────────────────────────────────


def test_get_single_task(client):
    created = _create(client, "Find me").get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["id"] == created["id"]
    assert body["title"] == "Find me"


def test_get_nonexistent_task_returns_404(client):
    resp = client.get("/tasks/9999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


# ── PUT /tasks/{id} ──────────────────────────────────────────


def test_update_title_only(client):
    created = _create(client, "old title").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "new title"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "new title"
    assert body["status"] == "pending"


def test_update_status_only(client):
    created = _create(client, "keep").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "in_progress"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "keep"
    assert body["status"] == "in_progress"


def test_update_title_and_status(client):
    created = _create(client, "keep").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "changed", "status": "done"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "changed"
    assert body["status"] == "done"


def test_update_nonexistent_task_returns_404(client):
    resp = client.put("/tasks/9999", json={"title": "nope"})
    assert resp.status_code == 404
    assert "error" in resp.get_json()
