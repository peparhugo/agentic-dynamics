import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test_todos.db"
    app_module.DATABASE = str(db_path)
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        yield client


def create(client, title="Buy milk"):
    return client.post("/tasks", json={"title": title})


def test_create_task_success(client):
    resp = create(client, "Buy milk")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert "id" in data
    assert "created_at" in data


def test_create_task_persists_pending_status(client):
    resp = create(client, "Buy milk")
    task_id = resp.get_json()["id"]
    fetched = client.get(f"/tasks/{task_id}").get_json()
    assert fetched["status"] == "pending"


def test_create_task_missing_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


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
    create(client, "first")
    time.sleep(0.01)
    create(client, "second")
    time.sleep(0.01)
    create(client, "third")

    resp = client.get("/tasks")
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["third", "second", "first"]


def test_get_task_success(client):
    created = create(client, "Buy milk").get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Buy milk"


def test_get_task_not_found(client):
    resp = client.get("/tasks/9999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title_and_status(client):
    created = create(client, "Buy milk").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "Buy oat milk", "status": "done"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Buy oat milk"
    assert data["status"] == "done"


def test_update_task_partial_status_only(client):
    created = create(client, "Buy milk").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "done"


def test_update_task_not_found(client):
    resp = client.put("/tasks/9999", json={"title": "x"})
    assert resp.status_code == 404
    assert "error" in resp.get_json()
