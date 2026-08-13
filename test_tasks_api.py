import json

import pytest

from tasks_api import create_app


@pytest.fixture
def client(tmp_path):
    storage_path = tmp_path / "tasks.json"
    app = create_app(storage_path=str(storage_path))
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def create_task(client, title="Buy milk"):
    return client.post("/tasks", json={"title": title})


# ── POST /tasks ─────────────────────────────────────────────────

def test_create_task_returns_201_with_task_fields(client):
    resp = create_task(client, "Buy milk")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["id"] == 1
    assert body["title"] == "Buy milk"
    assert body["status"] == "pending"
    assert "created_at" in body


def test_create_task_increments_id(client):
    first = create_task(client, "First").get_json()
    second = create_task(client, "Second").get_json()
    assert second["id"] == first["id"] + 1


def test_create_task_missing_title_returns_400(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_blank_title_returns_400(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400


def test_create_task_no_json_body_returns_400(client):
    resp = client.post("/tasks", data="not json", content_type="text/plain")
    assert resp.status_code == 400


def test_create_task_non_string_title_returns_400(client):
    resp = client.post("/tasks", json={"title": 123})
    assert resp.status_code == 400


# ── GET /tasks ──────────────────────────────────────────────────

def test_list_tasks_empty(client):
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_tasks_ordered_by_created_at_desc(client):
    create_task(client, "Oldest")
    create_task(client, "Middle")
    create_task(client, "Newest")

    resp = client.get("/tasks")
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["Newest", "Middle", "Oldest"]


# ── GET /tasks/{id} ─────────────────────────────────────────────

def test_get_task_found(client):
    created = create_task(client, "Buy milk").get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json() == created


def test_get_task_not_found_returns_404(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


# ── PUT /tasks/{id} ─────────────────────────────────────────────

def test_update_task_title(client):
    created = create_task(client, "Old title").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "New title"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "New title"
    assert body["status"] == "pending"


def test_update_task_status(client):
    created = create_task(client, "Task").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "done"
    assert body["title"] == "Task"


def test_update_task_title_and_status(client):
    created = create_task(client, "Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "Updated", "status": "done"}
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "Updated"
    assert body["status"] == "done"


def test_update_task_not_found_returns_404(client):
    resp = client.put("/tasks/999", json={"title": "x"})
    assert resp.status_code == 404


def test_update_task_empty_body_returns_400(client):
    created = create_task(client, "Task").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={})
    assert resp.status_code == 400


def test_update_task_blank_title_returns_400(client):
    created = create_task(client, "Task").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "   "})
    assert resp.status_code == 400


# ── Storage sanity ──────────────────────────────────────────────

def test_data_persisted_as_flat_json_file(client, tmp_path):
    create_task(client, "Persisted task")
    storage_path = tmp_path / "tasks.json"
    assert storage_path.exists()
    with open(storage_path) as f:
        data = json.load(f)
    assert data["tasks"][0]["title"] == "Persisted task"
