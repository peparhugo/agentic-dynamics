import os
import tempfile

import pytest

os.environ["DATABASE"] = "test_tasks.db"
import app as task_app

task_app.init_db()


@pytest.fixture()
def client():
    task_app.app.config["TESTING"] = True
    with task_app.app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def clean_db():
    yield
    with task_app.get_db() as conn:
        conn.execute("DELETE FROM tasks")
        conn.commit()


def test_create_task(client):
    resp = client.post("/tasks", json={"title": "Buy milk"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert data["id"] > 0
    assert "created_at" in data


def test_create_task_missing_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()

    resp = client.post("/tasks", json={"title": ""})
    assert resp.status_code == 400

    resp = client.post("/tasks")
    assert resp.status_code == 400


def test_list_tasks_ordered_by_created_at_desc(client):
    client.post("/tasks", json={"title": "first"})
    client.post("/tasks", json={"title": "second"})
    resp = client.get("/tasks")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2
    assert [t["title"] for t in data] == ["second", "first"]


def test_get_task(client):
    created = client.post("/tasks", json={"title": "Get task"}).get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Get task"


def test_get_task_not_found(client):
    resp = client.get("/tasks/9999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title_and_status(client):
    created = client.post("/tasks", json={"title": "Old"}).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "New", "status": "done"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New"
    assert data["status"] == "done"
    assert data["id"] == created["id"]


def test_update_task_partial(client):
    created = client.post("/tasks", json={"title": "Partial"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "in_progress"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Partial"
    assert data["status"] == "in_progress"


def test_update_task_not_found(client):
    resp = client.put("/tasks/9999", json={"title": "x"})
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_empty_list(client):
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert resp.get_json() == []
