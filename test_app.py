import importlib
import json
import os

import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    data_file = tmp_path / "tasks.json"
    monkeypatch.setenv("DATA_FILE", str(data_file))

    import app as app_module
    importlib.reload(app_module)
    app_module.init_db()

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def test_create_task_success(client):
    resp = client.post("/tasks", json={"title": "Buy milk"})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["id"] == 1
    assert body["title"] == "Buy milk"
    assert body["status"] == "pending"
    assert "created_at" in body


def test_create_task_missing_title_returns_400(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    body = resp.get_json()
    assert "error" in body


def test_create_task_blank_title_returns_400(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400


def test_create_task_no_body_returns_400(client):
    resp = client.post("/tasks")
    assert resp.status_code == 400


def test_list_tasks_ordered_desc_by_created_at(client):
    client.post("/tasks", json={"title": "first"})
    client.post("/tasks", json={"title": "second"})
    client.post("/tasks", json={"title": "third"})

    resp = client.get("/tasks")
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["third", "second", "first"]


def test_get_task_success(client):
    created = client.post("/tasks", json={"title": "Task A"}).get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Task A"


def test_get_task_not_found_returns_404(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title_and_status(client):
    created = client.post("/tasks", json={"title": "Old title"}).get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "New title", "status": "done"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "New title"
    assert body["status"] == "done"


def test_update_task_partial_status_only(client):
    created = client.post("/tasks", json={"title": "Keep title"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "in_progress"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "Keep title"
    assert body["status"] == "in_progress"


def test_update_task_not_found_returns_404(client):
    resp = client.put("/tasks/999", json={"title": "x"})
    assert resp.status_code == 404


def test_update_task_invalid_title_returns_400(client):
    created = client.post("/tasks", json={"title": "Original"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "  "})
    assert resp.status_code == 400


def test_storage_is_flat_json_file_not_database(client, monkeypatch):
    data_file = os.environ["DATA_FILE"]
    client.post("/tasks", json={"title": "flat file check"})
    assert os.path.exists(data_file)
    with open(data_file) as f:
        content = json.load(f)
    assert isinstance(content, list)
    assert content[0]["title"] == "flat file check"
    assert not os.path.exists("todos.db")
