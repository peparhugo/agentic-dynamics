import pytest

import app as app_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DATABASE", str(tmp_path / "tasks.db"))
    app_module.init_db()
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as test_client:
        yield test_client


def test_create_task_uses_pending_status_and_iso_timestamp(client):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    task = response.get_json()
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["id"] == 1
    assert "T" in task["created_at"]


def test_create_task_requires_title(client):
    response = client.post("/tasks", json={})

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_create_task_rejects_invalid_status(client):
    response = client.post("/tasks", json={"title": "Task", "status": "blocked"})

    assert response.status_code == 422
    assert response.get_json() == {
        "error": "status must be either 'pending' or 'done'"
    }


def test_list_tasks_is_ordered_newest_first(client):
    client.post("/tasks", json={"title": "First"})
    client.post("/tasks", json={"title": "Second"})

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["title"] for task in response.get_json()] == ["Second", "First"]


def test_get_task_returns_404_for_missing_task(client):
    response = client.get("/tasks/99")

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}


def test_update_task_title_and_status(client):
    created = client.post("/tasks", json={"title": "Old title"}).get_json()

    response = client.put(
        f"/tasks/{created['id']}",
        json={"title": "New title", "status": "done"},
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "New title"
    assert response.get_json()["status"] == "done"


def test_invalid_status_is_rejected(client):
    created = client.post("/tasks", json={"title": "Task"}).get_json()

    response = client.put(f"/tasks/{created['id']}", json={"status": "blocked"})

    assert response.status_code == 422
    assert response.get_json() == {
        "error": "status must be either 'pending' or 'done'"
    }


def test_update_missing_task_returns_404(client):
    response = client.put("/tasks/99", json={"title": "Missing"})

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}
