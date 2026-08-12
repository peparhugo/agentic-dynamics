import os
import tempfile

import pytest

from app import app, init_db


@pytest.fixture()
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    app.config.update(TESTING=True)

    import app as app_module
    app_module.DATABASE = path
    init_db()

    with app.test_client() as c:
        yield c

    os.unlink(path)


def test_create_task(client):
    res = client.post("/tasks", json={"title": "write code"})
    assert res.status_code == 201
    body = res.get_json()
    assert body["title"] == "write code"
    assert body["status"] == "pending"
    assert body["id"] == 1
    assert body["created_at"]


def test_create_task_missing_title(client):
    res = client.post("/tasks", json={})
    assert res.status_code == 400
    assert res.get_json()["error"]


def test_create_task_empty_title(client):
    res = client.post("/tasks", json={"title": "   "})
    assert res.status_code == 400
    assert res.get_json()["error"]


def test_create_task_no_json(client):
    res = client.post("/tasks", data="not json")
    assert res.status_code == 400
    assert res.get_json()["error"]


def test_list_tasks_ordered_desc(client):
    client.post("/tasks", json={"title": "first"})
    client.post("/tasks", json={"title": "second"})
    res = client.get("/tasks")
    assert res.status_code == 200
    tasks = res.get_json()
    assert len(tasks) == 2
    assert tasks[0]["title"] == "second"
    assert tasks[1]["title"] == "first"


def test_get_task(client):
    created = client.post("/tasks", json={"title": "hello"}).get_json()
    res = client.get(f"/tasks/{created['id']}")
    assert res.status_code == 200
    assert res.get_json()["title"] == "hello"


def test_get_task_not_found(client):
    res = client.get("/tasks/999")
    assert res.status_code == 404
    assert res.get_json()["error"]


def test_update_task_title_and_status(client):
    created = client.post("/tasks", json={"title": "hello"}).get_json()
    res = client.put(
        f"/tasks/{created['id']}",
        json={"title": "updated", "status": "done"},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["title"] == "updated"
    assert body["status"] == "done"


def test_update_task_not_found(client):
    res = client.put("/tasks/999", json={"title": "x"})
    assert res.status_code == 404
    assert res.get_json()["error"]


def test_update_task_partial(client):
    created = client.post("/tasks", json={"title": "hello"}).get_json()
    res = client.put(f"/tasks/{created['id']}", json={"status": "in_progress"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["title"] == "hello"
    assert body["status"] == "in_progress"
