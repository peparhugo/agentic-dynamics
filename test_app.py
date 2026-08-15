import importlib
import time

import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE", str(db_path))
    import app as app_module

    app_module.DATABASE = str(db_path)
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def test_create_task(client):
    resp = client.post("/tasks", json={"title": "first task"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "first task"
    assert data["status"] == "pending"
    assert isinstance(data["created_at"], int)
    assert data["id"] == 1


def test_create_task_missing_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_ordered_desc(client):
    client.post("/tasks", json={"title": "a"})
    time.sleep(1.1)
    client.post("/tasks", json={"title": "b"})
    resp = client.get("/tasks")
    assert resp.status_code == 200
    data = resp.get_json()
    assert [t["title"] for t in data] == ["b", "a"]


def test_get_task(client):
    client.post("/tasks", json={"title": "single"})
    resp = client.get("/tasks/1")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "single"


def test_get_task_not_found(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404


def test_update_task(client):
    client.post("/tasks", json={"title": "old"})
    resp = client.put("/tasks/1", json={"title": "new", "status": "done"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "new"
    assert data["status"] == "done"


def test_update_task_not_found(client):
    resp = client.put("/tasks/999", json={"title": "x"})
    assert resp.status_code == 404
