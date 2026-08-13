import pytest

import app as task_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    task_app.app.config.update(TESTING=True)
    return task_app.app.test_client()


def test_create_and_get_task(client):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    task = response.get_json()
    assert task["title"] == "Write tests"
    assert task["status"] == "pending"
    assert task["created_at"]
    assert client.get(f"/tasks/{task['id']}").get_json() == task


def test_list_tasks_newest_first(client):
    first = client.post("/tasks", json={"title": "First"}).get_json()
    second = client.post("/tasks", json={"title": "Second"}).get_json()

    assert [task["id"] for task in client.get("/tasks").get_json()] == [
        second["id"],
        first["id"],
    ]


def test_update_task(client):
    task_id = client.post("/tasks", json={"title": "Old"}).get_json()["id"]

    response = client.put(
        f"/tasks/{task_id}", json={"title": "New", "status": "complete"}
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "New"
    assert response.get_json()["status"] == "complete"


@pytest.mark.parametrize(
    "payload", [{}, {"title": ""}, {"title": "   "}, {"title": None}, {"title": 1}]
)
def test_create_requires_title(client, payload):
    response = client.post("/tasks", json=payload)

    assert response.status_code == 400
    assert "error" in response.get_json()


@pytest.mark.parametrize("method", ["get", "put"])
def test_missing_task_returns_404(client, method):
    kwargs = {"json": {"status": "complete"}} if method == "put" else {}
    response = getattr(client, method)("/tasks/999", **kwargs)

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}
