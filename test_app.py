import pytest

import app as app_module


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DATABASE", str(tmp_path / "test.db"))
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def _create(client, title):
    return client.post("/tasks", json={"title": title})


def test_create_task(client):
    resp = _create(client, "Buy milk")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert data["id"] == 1
    assert "created_at" in data


def test_create_task_missing_title_400(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_empty_title_400(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_ordered_by_created_at_desc(client):
    _create(client, "first")
    _create(client, "second")
    _create(client, "third")
    resp = client.get("/tasks")
    assert resp.status_code == 200
    tasks = resp.get_json()
    assert [t["title"] for t in tasks] == ["third", "second", "first"]


def test_get_single_task(client):
    created = _create(client, "Buy milk").get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Buy milk"


def test_get_task_not_found_404(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client):
    created = _create(client, "Old title").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "New title"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status(client):
    created = _create(client, "Buy milk").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "done"
    assert data["title"] == "Buy milk"


def test_update_task_title_and_status(client):
    created = _create(client, "Old title").get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "New title", "status": "in_progress"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "in_progress"


def test_update_task_not_found_404(client):
    resp = client.put("/tasks/999", json={"title": "nope"})
    assert resp.status_code == 404
    assert "error" in resp.get_json()
