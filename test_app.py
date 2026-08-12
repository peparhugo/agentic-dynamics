import os
import tempfile
import pytest

DATABASE = os.environ.get("TEST_DATABASE")

if DATABASE is None:
    _tmpdir = tempfile.mkdtemp()
    DATABASE = os.path.join(_tmpdir, "test_todos.db")

os.environ["DATABASE"] = DATABASE

import app as app_module

app_module.DATABASE = DATABASE
app_module.init_db()


@pytest.fixture(autouse=True)
def clean_db():
    yield
    with app_module.get_db() as conn:
        conn.execute("DELETE FROM tasks")
        conn.commit()


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_create_task(client):
    resp = client.post("/tasks", json={"title": "buy milk"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] > 0
    assert data["title"] == "buy milk"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_create_task_requires_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"]


def test_create_task_rejects_blank_title(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400


def test_list_tasks_ordered_desc(client):
    client.post("/tasks", json={"title": "first"})
    client.post("/tasks", json={"title": "second"})
    resp = client.get("/tasks")
    assert resp.status_code == 200
    tasks = resp.get_json()
    assert [t["title"] for t in tasks] == ["second", "first"]


def test_get_task(client):
    created = client.post("/tasks", json={"title": "hello"}).get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "hello"


def test_get_task_not_found(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert resp.get_json()["error"]


def test_update_task_title(client):
    created = client.post("/tasks", json={"title": "old"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "new"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "new"
    assert data["status"] == "pending"


def test_update_task_status(client):
    created = client.post("/tasks", json={"title": "task"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "done"


def test_update_task_both(client):
    created = client.post("/tasks", json={"title": "a"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "b", "status": "in_progress"})
    data = resp.get_json()
    assert data["title"] == "b"
    assert data["status"] == "in_progress"


def test_update_task_not_found(client):
    resp = client.put("/tasks/999", json={"title": "x"})
    assert resp.status_code == 404
    assert resp.get_json()["error"]
