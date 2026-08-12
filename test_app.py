import os
import sqlite3

import pytest

import app as app_module

app = app_module.app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_tasks.db")
    app_module.app.config["TESTING"] = True
    app_module.app.config["DATABASE"] = db_path
    app_module.init_db()
    with app_module.app.test_client() as c:
        yield c


def _create(client, title, status=None):
    body = {"title": title}
    if status is not None:
        body["status"] = status
    return client.post("/tasks", json=body)


def test_create_task(client):
    resp = _create(client, "buy milk")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "buy milk"
    assert data["status"] == "pending"
    assert isinstance(data["id"], int)
    assert data["created_at"]


def test_create_task_missing_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_empty_title(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_with_status(client):
    resp = _create(client, "ship it", status="done")
    assert resp.status_code == 201
    assert resp.get_json()["status"] == "done"


def test_list_tasks_ordered_by_created_at_desc(client):
    _create(client, "first")
    _create(client, "second")
    _create(client, "third")
    resp = client.get("/tasks")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 3
    assert data[0]["title"] == "third"
    assert data[1]["title"] == "second"
    assert data[2]["title"] == "first"


def test_get_task(client):
    created = _create(client, "groceries").get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == created["id"]
    assert data["title"] == "groceries"


def test_get_task_not_found(client):
    resp = client.get("/tasks/9999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client):
    created = _create(client, "old title").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "new title"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "new title"
    assert data["status"] == "pending"


def test_update_task_status(client):
    created = _create(client, "task").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "in_progress"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "in_progress"
    assert data["title"] == "task"


def test_update_task_title_and_status(client):
    created = _create(client, "a").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "b", "status": "completed"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "b"
    assert data["status"] == "completed"


def test_update_task_not_found(client):
    resp = client.put("/tasks/9999", json={"title": "x"})
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_tasks_table_exists_with_expected_schema(client, tmp_path):
    conn = sqlite3.connect(app_module.get_database_path())
    cols = {
        r[1]: r[2]
        for r in conn.execute("PRAGMA table_info(tasks)").fetchall()
    }
    assert set(cols) == {"id", "title", "status", "created_at"}
    assert cols["id"] == "INTEGER"
    assert cols["title"] == "TEXT"
    assert cols["status"] == "TEXT"
    assert cols["created_at"] == "TEXT"
    conn.close()


def test_error_handler_returns_json(client):
    resp = client.get("/tasks/not-an-int")
    assert resp.status_code in (404, 405)
    assert resp.is_json
