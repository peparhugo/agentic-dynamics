import os
import tempfile

import pytest

import app as task_app


@pytest.fixture()
def client():
    task_app.app.config["TESTING"] = True
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    task_app.DATABASE = db_path
    task_app.init_db()
    with task_app.app.test_client() as c:
        yield c
    os.unlink(db_path)


def test_create_task(client):
    resp = client.post("/tasks", json={"title": "Write code"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Write code"
    assert data["status"] == "pending"
    assert isinstance(data["id"], int)
    assert data["created_at"]


def test_create_task_missing_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_ordered_by_created_at_desc(client):
    client.post("/tasks", json={"title": "first"})
    client.post("/tasks", json={"title": "second"})
    client.post("/tasks", json={"title": "third"})
    resp = client.get("/tasks")
    assert resp.status_code == 200
    tasks = resp.get_json()
    assert [t["title"] for t in tasks] == ["third", "second", "first"]


def test_get_task(client):
    created = client.post("/tasks", json={"title": "Find me"}).get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Find me"


def test_get_task_not_found(client):
    resp = client.get("/tasks/9999")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "task not found"}


def test_update_task(client):
    created = client.post("/tasks", json={"title": "Old title"}).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "New title", "status": "done"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "done"
    assert data["id"] == created["id"]


def test_update_task_partial(client):
    created = client.post("/tasks", json={"title": "Keep me"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "in_progress"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Keep me"
    assert data["status"] == "in_progress"


def test_update_task_not_found(client):
    resp = client.put("/tasks/9999", json={"title": "nope"})
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "task not found"}
