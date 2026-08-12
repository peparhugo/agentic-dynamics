import importlib

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_tasks.db")
    monkeypatch.setenv("DATABASE", db_file)
    app = importlib.import_module("app")
    monkeypatch.setattr(app, "DATABASE", db_file)
    app.init_db()
    app.app.config["TESTING"] = True
    with app.app.test_client() as c:
        yield c


def _create(client, title):
    return client.post("/tasks", json={"title": title})


def test_create_task(client):
    resp = _create(client, "Buy milk")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_create_task_missing_title_returns_400(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_empty_title_returns_400(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_missing_body_returns_400(client):
    resp = client.post("/tasks", data="")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_assigns_incrementing_ids(client):
    for i in range(1, 4):
        resp = _create(client, f"task {i}")
        assert resp.status_code == 201
        assert resp.get_json()["id"] == i


def test_list_tasks_ordered_by_created_at_desc(client):
    for i in range(1, 4):
        _create(client, f"task {i}")
    resp = client.get("/tasks")
    assert resp.status_code == 200
    data = resp.get_json()
    assert [t["title"] for t in data] == ["task 3", "task 2", "task 1"]


def test_list_tasks_empty(client):
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_get_task(client):
    created = _create(client, "Buy milk").get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"


def test_get_task_not_found_returns_404(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title_and_status(client):
    created = _create(client, "Buy milk").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"title": "Buy almond milk", "status": "done"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Buy almond milk"
    assert data["status"] == "done"


def test_update_task_title_only(client):
    created = _create(client, "Buy milk").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "New title"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status_only(client):
    created = _create(client, "Buy milk").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "in_progress"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "in_progress"


def test_update_task_not_found_returns_404(client):
    resp = client.put("/tasks/999", json={"title": "x"})
    assert resp.status_code == 404
    assert "error" in resp.get_json()
