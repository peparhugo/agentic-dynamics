import os
import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE", str(db_path))
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def _create(client, title):
    return client.post("/tasks", json={"title": title})


def test_create_task(client):
    resp = _create(client, "Buy milk")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert "id" in data
    assert "created_at" in data


def test_create_task_missing_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_empty_title(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400


def test_list_tasks_ordered_by_created_at_desc(client):
    first = _create(client, "first").get_json()
    second = _create(client, "second").get_json()
    tasks = client.get("/tasks").get_json()
    assert len(tasks) == 2
    assert tasks[0]["id"] == second["id"]
    assert tasks[1]["id"] == first["id"]


def test_get_single_task(client):
    created = _create(client, "single").get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json() == created


def test_get_task_not_found(client):
    resp = client.get("/tasks/9999")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "task not found"}


def test_update_title_and_status(client):
    created = _create(client, "old").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "new", "status": "done"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "new"
    assert data["status"] == "done"
    assert data["id"] == created["id"]


def test_update_status_only(client):
    created = _create(client, "keep").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "in_progress"})
    data = resp.get_json()
    assert data["title"] == "keep"
    assert data["status"] == "in_progress"


def test_update_task_not_found(client):
    resp = client.put("/tasks/9999", json={"title": "x"})
    assert resp.status_code == 404


def test_default_status_is_pending(client):
    _create(client, "a")
    assert client.get("/tasks").get_json()[0]["status"] == "pending"
