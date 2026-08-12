import os
import time

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE", str(tmp_path / "test.db"))
    import importlib
    import app as app_module

    app_module = importlib.reload(app_module)
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def post_task(client, title):
    return client.post("/tasks", json={"title": title})


def test_create_task(client):
    rv = post_task(client, "Write code")
    assert rv.status_code == 201
    data = rv.get_json()
    assert data["id"] > 0
    assert data["title"] == "Write code"
    assert data["status"] == "pending"
    assert isinstance(data["created_at"], int)


def test_create_task_missing_title_returns_400(client):
    rv = client.post("/tasks", json={})
    assert rv.status_code == 400
    assert "error" in rv.get_json()

    rv = client.post("/tasks", json={"title": "   "})
    assert rv.status_code == 400


def test_list_tasks_ordered_by_created_at_desc(client):
    post_task(client, "first")
    time.sleep(1.1)
    post_task(client, "second")
    time.sleep(1.1)
    post_task(client, "third")

    rv = client.get("/tasks")
    assert rv.status_code == 200
    tasks = rv.get_json()
    assert [t["title"] for t in tasks] == ["third", "second", "first"]
    assert [t["created_at"] for t in tasks] == sorted(
        (t["created_at"] for t in tasks), reverse=True
    )


def test_get_task(client):
    created = post_task(client, "Fetch me").get_json()
    rv = client.get(f"/tasks/{created['id']}")
    assert rv.status_code == 200
    assert rv.get_json() == created


def test_get_task_not_found_returns_404(client):
    rv = client.get("/tasks/9999")
    assert rv.status_code == 404
    assert "error" in rv.get_json()


def test_update_task_title_and_status(client):
    created = post_task(client, "Original").get_json()
    tid = created["id"]

    rv = client.put(f"/tasks/{tid}", json={"title": "Updated", "status": "done"})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["title"] == "Updated"
    assert data["status"] == "done"

    rv = client.put(f"/tasks/{tid}", json={"title": "Only title"})
    assert rv.get_json()["title"] == "Only title"
    assert rv.get_json()["status"] == "done"

    rv = client.put(f"/tasks/{tid}", json={"status": "in_progress"})
    assert rv.get_json()["status"] == "in_progress"
    assert rv.get_json()["title"] == "Only title"


def test_update_task_not_found_returns_404(client):
    rv = client.put("/tasks/9999", json={"status": "done"})
    assert rv.status_code == 404
    assert "error" in rv.get_json()
