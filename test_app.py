import json

import app
import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "DATA_FILE", str(tmp_path / "tasks.json"))
    app.init_db()
    return app.app.test_client()


def test_create_task_uses_pending_status(client):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    task = response.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]


@pytest.mark.parametrize("payload", ({}, {"title": ""}, {"title": 3}))
def test_create_task_requires_a_title(client, payload):
    response = client.post("/tasks", json=payload)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_orders_newest_first(client):
    client.post("/tasks", json={"title": "First"})
    client.post("/tasks", json={"title": "Second"})

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["title"] for task in response.get_json()] == ["Second", "First"]


def test_get_and_update_task(client):
    created = client.post("/tasks", json={"title": "Draft"}).get_json()

    response = client.put(
        f"/tasks/{created['id']}", json={"title": "Published", "status": "done"}
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "Published"
    assert response.get_json()["status"] == "done"
    assert client.get(f"/tasks/{created['id']}").get_json() == response.get_json()


def test_missing_task_returns_json_404(client):
    response = client.get("/tasks/99")

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_tasks_are_persisted_to_flat_file(client, tmp_path):
    client.post("/tasks", json={"title": "Persisted"})

    assert json.loads((tmp_path / "tasks.json").read_text()) == [
        {
            "id": 1,
            "title": "Persisted",
            "status": "pending",
            "created_at": app.get_task(1)["created_at"],
        }
    ]
