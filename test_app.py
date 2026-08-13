import app as task_app

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    task_app.app.config.update(TESTING=True)
    return task_app.app.test_client()


def test_create_and_get_task(client):
    created = client.post("/tasks", json={"title": "Write tests"})

    assert created.status_code == 201
    task = created.get_json()
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]

    fetched = client.get(f"/tasks/{task['id']}")
    assert fetched.status_code == 200
    assert fetched.get_json() == task


def test_list_orders_newest_task_first(client):
    first = client.post("/tasks", json={"title": "First"}).get_json()
    second = client.post("/tasks", json={"title": "Second"}).get_json()

    tasks = client.get("/tasks").get_json()
    assert [task["id"] for task in tasks] == [second["id"], first["id"]]


def test_update_task(client):
    task = client.post("/tasks", json={"title": "Draft"}).get_json()

    response = client.put(
        f"/tasks/{task['id']}", json={"title": "Published", "status": "complete"}
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "Published"
    assert response.get_json()["status"] == "complete"


@pytest.mark.parametrize("payload", [{}, {"title": ""}, {"title": 42}])
def test_create_requires_a_title(client, payload):
    response = client.post("/tasks", json=payload)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_missing_task_returns_json_404(client):
    response = client.get("/tasks/999")

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}
