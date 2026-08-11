import os
import tempfile
import pytest

db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
os.environ["DATABASE"] = db_file.name

import app


@pytest.fixture
def client():
    app.init_db()
    with app.app.test_client() as client:
        yield client
    conn = app.get_db()
    conn.execute("DROP TABLE IF EXISTS tasks")
    conn.commit()
    conn.close()


def test_create_task(client):
    resp = client.post("/tasks", json={"title": "Buy groceries"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Buy groceries"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_list_tasks_empty(client):
    resp = client.get("/tasks")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == []


def test_list_tasks_ordered(client):
    client.post("/tasks", json={"title": "Task 1"})
    client.post("/tasks", json={"title": "Task 2"})
    client.post("/tasks", json={"title": "Task 3"})
    resp = client.get("/tasks")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 3
    assert data[0]["title"] == "Task 3"
    assert data[1]["title"] == "Task 2"
    assert data[2]["title"] == "Task 1"


def test_get_single_task(client):
    resp = client.post("/tasks", json={"title": "Read book"})
    task_id = resp.get_json()["id"]
    resp = client.get(f"/tasks/{task_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == task_id
    assert data["title"] == "Read book"
    assert data["status"] == "pending"


def test_get_task_not_found(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_update_task_title(client):
    resp = client.post("/tasks", json={"title": "Old title"})
    task_id = resp.get_json()["id"]
    resp = client.put(f"/tasks/{task_id}", json={"title": "New title"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status(client):
    resp = client.post("/tasks", json={"title": "Do laundry"})
    task_id = resp.get_json()["id"]
    resp = client.put(f"/tasks/{task_id}", json={"status": "done"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "done"


def test_update_task_both(client):
    resp = client.post("/tasks", json={"title": "Walk dog"})
    task_id = resp.get_json()["id"]
    resp = client.put(f"/tasks/{task_id}", json={"title": "Walk cat", "status": "in_progress"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Walk cat"
    assert data["status"] == "in_progress"


def test_update_task_not_found(client):
    resp = client.put("/tasks/999", json={"title": "Nope"})
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_update_task_no_fields(client):
    resp = client.post("/tasks", json={"title": "Test"})
    task_id = resp.get_json()["id"]
    resp = client.put(f"/tasks/{task_id}", json={})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Test"
    assert data["status"] == "pending"


def test_post_missing_json(client):
    resp = client.post("/tasks", data="", content_type="application/json")
    assert resp.status_code == 400


def test_multiple_tasks_increment_ids(client):
    r1 = client.post("/tasks", json={"title": "A"})
    r2 = client.post("/tasks", json={"title": "B"})
    r3 = client.post("/tasks", json={"title": "C"})
    assert r1.get_json()["id"] == 1
    assert r2.get_json()["id"] == 2
    assert r3.get_json()["id"] == 3
