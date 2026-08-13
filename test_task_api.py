import json

import pytest

from task_api import create_app


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / "test_tasks.db"
    return create_app(str(db_path))


@pytest.fixture
def client(app):
    return app.test_client()


def create_task(client, title="Write tests", **extra):
    body = {"title": title, **extra}
    return client.post("/tasks", data=json.dumps(body), content_type="application/json")


# ── POST /tasks ──────────────────────────────────────────────────


def test_create_task_success(client):
    resp = create_task(client, title="Buy milk")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert isinstance(data["id"], int)
    assert "created_at" in data and data["created_at"]


def test_create_task_missing_title_returns_400(client):
    resp = client.post("/tasks", data=json.dumps({}), content_type="application/json")
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_create_task_blank_title_returns_400(client):
    resp = create_task(client, title="   ")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_non_string_title_returns_400(client):
    resp = create_task(client, title=123)
    assert resp.status_code == 400


def test_create_task_invalid_status_returns_400(client):
    resp = create_task(client, title="Task", status="bogus")
    assert resp.status_code == 400


def test_create_task_no_body_returns_400(client):
    resp = client.post("/tasks", content_type="application/json")
    assert resp.status_code == 400


def test_create_task_non_json_body_returns_400(client):
    resp = client.post("/tasks", data="not json", content_type="application/json")
    assert resp.status_code == 400


def test_create_task_strips_whitespace(client):
    resp = create_task(client, title="  padded title  ")
    assert resp.status_code == 201
    assert resp.get_json()["title"] == "padded title"


# ── GET /tasks ───────────────────────────────────────────────────


def test_list_tasks_empty(client):
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_tasks_ordered_desc_by_created_at(client):
    ids = []
    for title in ["first", "second", "third"]:
        resp = create_task(client, title=title)
        ids.append(resp.get_json()["id"])

    resp = client.get("/tasks")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 3
    returned_ids = [t["id"] for t in data]
    assert returned_ids == list(reversed(ids))
    assert [t["title"] for t in data] == ["third", "second", "first"]


# ── GET /tasks/<id> ──────────────────────────────────────────────


def test_get_task_success(client):
    created = create_task(client, title="Read book").get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json() == created


def test_get_task_not_found_returns_404(client):
    resp = client.get("/tasks/9999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


# ── PUT /tasks/<id> ──────────────────────────────────────────────


def test_update_task_title_only(client):
    created = create_task(client, title="Old title").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"title": "New title"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status_only(client):
    created = create_task(client, title="Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "completed"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "completed"
    assert data["title"] == "Task"


def test_update_task_title_and_status(client):
    created = create_task(client, title="Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"title": "Updated", "status": "in_progress"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Updated"
    assert data["status"] == "in_progress"


def test_update_task_not_found_returns_404(client):
    resp = client.put(
        "/tasks/9999",
        data=json.dumps({"title": "x"}),
        content_type="application/json",
    )
    assert resp.status_code == 404


def test_update_task_blank_title_returns_400(client):
    created = create_task(client, title="Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"title": "   "}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_update_task_invalid_status_returns_400(client):
    created = create_task(client, title="Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({"status": "not-a-real-status"}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_update_task_empty_body_is_noop(client):
    created = create_task(client, title="Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == created["title"]
    assert data["status"] == created["status"]


# ── Misc ─────────────────────────────────────────────────────────


def test_persists_across_requests(client):
    created = create_task(client, title="Persisted").get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Persisted"
