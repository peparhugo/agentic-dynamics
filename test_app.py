import json

import pytest

import app as task_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.json"))
    task_app.init_db()
    task_app.app.config.update(TESTING=True)
    return task_app.app.test_client()


def test_storage_is_initialized_as_flat_file(tmp_path, monkeypatch):
    data_file = tmp_path / "data" / "tasks.json"
    monkeypatch.setattr(task_app, "DATABASE", str(data_file))

    task_app.init_db()

    assert json.loads(data_file.read_text()) == {"next_id": 1, "tasks": []}


def test_create_and_get_task(client):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    task = response.get_json()
    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]
    assert client.get("/tasks/1").get_json() == task


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "   "}, {"title": 12}])
def test_create_requires_title(client, body):
    response = client.post("/tasks", json=body)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_newest_first(client, monkeypatch):
    timestamps = iter([
        "2026-01-01T00:00:00+00:00",
        "2026-01-02T00:00:00+00:00",
    ])

    class Clock:
        @staticmethod
        def now(_timezone):
            return type("Moment", (), {"isoformat": lambda self: next(timestamps)})()

    monkeypatch.setattr(task_app, "datetime", Clock)
    client.post("/tasks", json={"title": "Older"})
    client.post("/tasks", json={"title": "Newer"})

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["title"] for task in response.get_json()] == ["Newer", "Older"]


def test_update_title_and_status(client):
    task_id = client.post("/tasks", json={"title": "Original"}).get_json()["id"]

    response = client.put(f"/tasks/{task_id}", json={"title": "Updated", "status": "done"})

    assert response.status_code == 200
    assert response.get_json()["title"] == "Updated"
    assert response.get_json()["status"] == "done"


def test_update_single_field_preserves_other_values(client):
    task = client.post("/tasks", json={"title": "Keep me"}).get_json()

    response = client.put(f"/tasks/{task['id']}", json={"status": "active"})

    assert response.get_json()["title"] == "Keep me"
    assert response.get_json()["status"] == "active"


@pytest.mark.parametrize("method", ["get", "put"])
def test_missing_task_returns_json_404(client, method):
    kwargs = {"json": {"status": "done"}} if method == "put" else {}

    response = getattr(client, method)("/tasks/999", **kwargs)

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}
