import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path):
    app_module.DATABASE = str(tmp_path / "test.db")
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def test_create_task(client):
    resp = client.post("/tasks", json={"title": "Buy milk"})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["title"] == "Buy milk"
    assert body["status"] == "pending"
    assert isinstance(body["id"], int)
    assert "created_at" in body


def test_create_task_missing_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_empty_title(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_no_body(client):
    resp = client.post("/tasks")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_empty(client):
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_tasks_ordered_desc(client):
    client.post("/tasks", json={"title": "first"})
    client.post("/tasks", json={"title": "second"})
    client.post("/tasks", json={"title": "third"})

    resp = client.get("/tasks")
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["third", "second", "first"]


def test_get_task(client):
    created = client.post("/tasks", json={"title": "Task A"}).get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json() == created


def test_get_task_not_found(client):
    resp = client.get("/tasks/9999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client):
    created = client.post("/tasks", json={"title": "Old title"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "New title"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "New title"
    assert body["status"] == "pending"


def test_update_task_status(client):
    created = client.post("/tasks", json={"title": "Task"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "done"
    assert body["title"] == "Task"


def test_update_task_title_and_status(client):
    created = client.post("/tasks", json={"title": "Task"}).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "Updated", "status": "done"}
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "Updated"
    assert body["status"] == "done"


def test_update_task_invalid_status(client):
    created = client.post("/tasks", json={"title": "Task"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "archived"})
    assert resp.status_code == 422
    assert "error" in resp.get_json()

    # task must remain unchanged
    unchanged = client.get(f"/tasks/{created['id']}").get_json()
    assert unchanged["status"] == "pending"


def test_update_task_not_found(client):
    resp = client.put("/tasks/9999", json={"title": "x"})
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_created_at_is_iso_string(client):
    created = client.post("/tasks", json={"title": "Task"}).get_json()
    assert isinstance(created["created_at"], str)
    from datetime import datetime

    datetime.fromisoformat(created["created_at"])
