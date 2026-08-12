import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

import app as app_module


@pytest.fixture()
def client(tmp_path):
    app_module.app.config["TESTING"] = True
    app_module.app.config["DATABASE"] = str(tmp_path / "test_tasks.db")
    app_module.init_db()
    with app_module.app.test_client() as client:
        yield client


def test_create_task(client):
    resp = client.post("/tasks", json={"title": "write docs"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "write docs"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_create_task_missing_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()

    resp = client.post("/tasks", json={"title": ""})
    assert resp.status_code == 400

    resp = client.post("/tasks", data="not json", content_type="text/plain")
    assert resp.status_code == 400


def test_list_tasks_ordered_desc(client):
    client.post("/tasks", json={"title": "first"})
    client.post("/tasks", json={"title": "second"})
    client.post("/tasks", json={"title": "third"})
    resp = client.get("/tasks")
    assert resp.status_code == 200
    tasks = resp.get_json()
    assert [t["title"] for t in tasks] == ["third", "second", "first"]
    assert [t["id"] for t in tasks] == [3, 2, 1]


def test_get_task(client):
    created = client.post("/tasks", json={"title": "read"})
    task_id = created.get_json()["id"]
    resp = client.get(f"/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "read"


def test_get_task_not_found(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task(client):
    created = client.post("/tasks", json={"title": "old"})
    task_id = created.get_json()["id"]

    resp = client.put(f"/tasks/{task_id}", json={"title": "new", "status": "done"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "new"
    assert data["status"] == "done"

    resp = client.put(f"/tasks/{task_id}", json={"status": "in_progress"})
    data = resp.get_json()
    assert data["title"] == "new"
    assert data["status"] == "in_progress"


def test_update_task_not_found(client):
    resp = client.put("/tasks/999", json={"title": "x"})
    assert resp.status_code == 404
    assert "error" in resp.get_json()
