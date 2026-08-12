import os
import tempfile

import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path):
    app_module.DATA_FILE = str(tmp_path / "tasks.json")
    app_module.init_store()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_create_task(client):
    resp = client.post("/tasks", json={"title": "Buy milk"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert data["id"] == 1
    assert data["created_at"]


def test_create_task_missing_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "title is required"}


def test_create_task_blank_title(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "title is required"}


def test_list_tasks_ordered_desc(client):
    client.post("/tasks", json={"title": "first"})
    client.post("/tasks", json={"title": "second"})
    resp = client.get("/tasks")
    assert resp.status_code == 200
    tasks = resp.get_json()
    assert [t["title"] for t in tasks] == ["second", "first"]
    assert [t["id"] for t in tasks] == [2, 1]


def test_get_task(client):
    created = client.post("/tasks", json={"title": "Get me"}).get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Get me"


def test_get_task_not_found(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "task not found"}


def test_update_task(client):
    created = client.post("/tasks", json={"title": "Old"}).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "New", "status": "done"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New"
    assert data["status"] == "done"


def test_update_task_title_only(client):
    created = client.post("/tasks", json={"title": "Old"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "New"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New"
    assert data["status"] == "pending"


def test_update_task_status_only(client):
    created = client.post("/tasks", json={"title": "Old"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Old"
    assert data["status"] == "done"


def test_update_task_not_found(client):
    resp = client.put("/tasks/999", json={"title": "Nope"})
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "task not found"}


def test_storage_persists_to_flat_file(client):
    client.post("/tasks", json={"title": "Persist me"})
    assert os.path.exists(app_module.DATA_FILE)
    with open(app_module.DATA_FILE, "r", encoding="utf-8") as fh:
        import json

        data = json.load(fh)
    assert data["tasks"][0]["title"] == "Persist me"
