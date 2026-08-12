import os
import pytest

from task_api import app, init_db

os.environ["TASK_DATABASE"] = "test_tasks.db"
import task_api

task_api.DATABASE = "test_tasks.db"


@pytest.fixture()
def client(tmp_path):
    task_api.DATABASE = str(tmp_path / "test_tasks.db")
    init_db()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_create_task(client):
    resp = client.post("/tasks", json={"title": "Buy milk"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_create_task_missing_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "title is required"


def test_create_task_blank_title(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "title is required"


def test_list_tasks_ordered_by_created_at_desc(client):
    client.post("/tasks", json={"title": "first"})
    client.post("/tasks", json={"title": "second"})
    client.post("/tasks", json={"title": "third"})
    resp = client.get("/tasks")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 3
    titles = [t["title"] for t in data]
    assert titles == ["third", "second", "first"]


def test_get_task(client):
    created = client.post("/tasks", json={"title": "Buy milk"}).get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Buy milk"


def test_get_task_not_found(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "task not found"


def test_update_task_title(client):
    created = client.post("/tasks", json={"title": "Buy milk"}).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "Buy oat milk"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Buy oat milk"
    assert data["status"] == "pending"


def test_update_task_status(client):
    created = client.post("/tasks", json={"title": "Buy milk"}).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"


def test_update_task_not_found(client):
    resp = client.put("/tasks/999", json={"title": "x"})
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "task not found"


def test_update_task_invalid_status(client):
    created = client.post("/tasks", json={"title": "Buy milk"}).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"status": "nonsense"}
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid status"


def test_update_task_blank_title(client):
    created = client.post("/tasks", json={"title": "Buy milk"}).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "  "}
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "title is required"


def test_json_error_message_shape(client):
    resp = client.post("/tasks", json={"title": ""})
    body = resp.get_json()
    assert resp.status_code == 400
    assert isinstance(body, dict)
    assert "error" in body
