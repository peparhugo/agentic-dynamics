import sqlite3

import pytest

import app as task_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "test.db"))
    task_app.init_db()
    task_app.app.config.update(TESTING=True)
    return task_app.app.test_client()


def test_create_task(client):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    assert response.get_json()["id"] == 1
    assert response.get_json()["status"] == "pending"
    assert response.get_json()["title"] == "Write tests"
    assert response.get_json()["created_at"]


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "   "}, {"title": 3}])
def test_create_requires_title(client, body):
    response = client.post("/tasks", json=body)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_ids_are_assigned_from_max_existing_id(client):
    with sqlite3.connect(task_app.DATABASE) as connection:
        connection.execute(
            "INSERT INTO tasks (id, title, status, created_at) VALUES (?, ?, ?, ?)",
            (8, "Existing", "pending", "2026-01-01T00:00:00+00:00"),
        )

    response = client.post("/tasks", json={"title": "Next"})

    assert response.get_json()["id"] == 9


def test_list_tasks_newest_first(client):
    first = client.post("/tasks", json={"title": "First"}).get_json()
    second = client.post("/tasks", json={"title": "Second"}).get_json()

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["id"] for task in response.get_json()] == [second["id"], first["id"]]


def test_get_task(client):
    created = client.post("/tasks", json={"title": "Read me"}).get_json()

    response = client.get(f"/tasks/{created['id']}")

    assert response.status_code == 200
    assert response.get_json() == created


def test_get_missing_task(client):
    response = client.get("/tasks/100")

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_update_title_and_status(client):
    created = client.post("/tasks", json={"title": "Old"}).get_json()

    response = client.put(
        f"/tasks/{created['id']}", json={"title": "New", "status": "done"}
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "New"
    assert response.get_json()["status"] == "done"


def test_update_one_field_preserves_the_other(client):
    created = client.post("/tasks", json={"title": "Original"}).get_json()

    response = client.put(f"/tasks/{created['id']}", json={"status": "active"})

    assert response.status_code == 200
    assert response.get_json()["title"] == "Original"
    assert response.get_json()["status"] == "active"


def test_update_missing_task(client):
    response = client.put("/tasks/100", json={"status": "done"})

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_update_requires_supported_field(client):
    created = client.post("/tasks", json={"title": "Original"}).get_json()

    response = client.put(f"/tasks/{created['id']}", json={})

    assert response.status_code == 400
    assert response.is_json
