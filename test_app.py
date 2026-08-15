import json
import os
import tempfile

import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path):
    app_module.DATA_FILE = str(tmp_path / "tasks.json")
    app_module.init_store()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def test_create_task(client):
    resp = client.post("/tasks", json={"title": "Buy milk"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert data["id"] == 1


def test_create_task_missing_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_blank_title(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400


def test_list_tasks_ordered_desc(client):
    client.post("/tasks", json={"title": "first"})
    client.post("/tasks", json={"title": "second"})
    resp = client.get("/tasks")
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["second", "first"]


def test_get_task(client):
    created = client.post("/tasks", json={"title": "alpha"}).get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "alpha"


def test_get_task_not_found(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task(client):
    created = client.post("/tasks", json={"title": "alpha"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "beta", "status": "done"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "beta"
    assert data["status"] == "done"


def test_update_task_partial(client):
    created = client.post("/tasks", json={"title": "alpha"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "in_progress"})
    data = resp.get_json()
    assert data["status"] == "in_progress"
    assert data["title"] == "alpha"


def test_update_task_not_found(client):
    resp = client.put("/tasks/999", json={"title": "x"})
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_persists_to_flat_file(client):
    client.post("/tasks", json={"title": "persisted"})
    with open(app_module.DATA_FILE) as f:
        store = json.load(f)
    assert any(t["title"] == "persisted" for t in store["tasks"])
