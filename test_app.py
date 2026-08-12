import sqlite3

import pytest

import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(app, "DATABASE", str(database))
    app.init_db()
    return app.app.test_client()


def test_create_and_list_tasks(client):
    response = client.post("/tasks", json={"title": "First task"})

    assert response.status_code == 201
    assert response.get_json()["status"] == "pending"
    assert client.get("/tasks").get_json()[0]["title"] == "First task"


def test_missing_title_returns_json_error(client):
    response = client.post("/tasks", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_get_and_update_task(client):
    task = client.post("/tasks", json={"title": "Initial"}).get_json()

    response = client.put(f"/tasks/{task['id']}", json={"title": "Updated", "status": "done"})

    assert response.status_code == 200
    assert response.get_json()["title"] == "Updated"
    assert response.get_json()["status"] == "done"
    assert client.get(f"/tasks/{task['id']}").get_json()["title"] == "Updated"


def test_missing_task_returns_json_404(client):
    response = client.get("/tasks/999")
    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}

    response = client.put("/tasks/999", json={"status": "done"})
    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_database_uses_wal(client, tmp_path, monkeypatch):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(app, "DATABASE", str(database))
    app.init_db()

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
