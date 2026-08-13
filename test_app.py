import sqlite3

import pytest

import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(app, "DATABASE", str(database))
    app.init_db()
    app.app.config.update(TESTING=True)
    return app.app.test_client()


def test_create_task_uses_pending_status(client):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    task = response.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]


@pytest.mark.parametrize("payload", [{}, {"title": ""}, {"title": "   "}, {"title": 1}])
def test_create_task_requires_a_title(client, payload):
    response = client.post("/tasks", json=payload)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_orders_newest_first(client):
    first = client.post("/tasks", json={"title": "First"}).get_json()
    second = client.post("/tasks", json={"title": "Second"}).get_json()

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["id"] for task in response.get_json()] == [second["id"], first["id"]]


def test_get_task_and_missing_task(client):
    task = client.post("/tasks", json={"title": "Read docs"}).get_json()

    response = client.get(f"/tasks/{task['id']}")
    assert response.status_code == 200
    assert response.get_json() == task

    missing = client.get("/tasks/999")
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "task not found"}


def test_update_task_title_and_status(client):
    task = client.post("/tasks", json={"title": "Draft"}).get_json()

    response = client.put(
        f"/tasks/{task['id']}", json={"title": "Published", "status": "done"}
    )

    assert response.status_code == 200
    assert response.get_json() == {**task, "title": "Published", "status": "done"}


def test_update_missing_task_returns_json_error(client):
    response = client.put("/tasks/999", json={"status": "done"})

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_schema_is_initialized():
    with app.get_db() as connection:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'tasks'"
        ).fetchone()
    assert table is not None
