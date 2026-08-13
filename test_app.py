import app as task_app
import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    task_app.app.config.update(TESTING=True)
    return task_app.app.test_client()


def test_create_task(client):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    assert response.json["title"] == "Write tests"
    assert response.json["status"] == "pending"
    assert response.json["id"] == 1
    assert response.json["created_at"]


@pytest.mark.parametrize("body", [{}, {"title": "  "}, {"title": 12}])
def test_create_requires_title(client, body):
    response = client.post("/tasks", json=body)

    assert response.status_code == 400
    assert response.json == {"error": "title is required"}


def test_list_tasks_newest_first(client):
    first = client.post("/tasks", json={"title": "First"}).json
    second = client.post("/tasks", json={"title": "Second"}).json

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["id"] for task in response.json] == [second["id"], first["id"]]


def test_get_task(client):
    created = client.post("/tasks", json={"title": "Read me"}).json

    response = client.get(f"/tasks/{created['id']}")

    assert response.status_code == 200
    assert response.json == created


def test_missing_task_returns_404(client):
    for method in (client.get, client.put):
        response = method("/tasks/999", json={} if method == client.put else None)
        assert response.status_code == 404
        assert response.json == {"error": "task not found"}


def test_update_task(client):
    created = client.post("/tasks", json={"title": "Old title"}).json

    response = client.put(
        f"/tasks/{created['id']}", json={"title": "New title", "status": "done"}
    )

    assert response.status_code == 200
    assert response.json["title"] == "New title"
    assert response.json["status"] == "done"
    assert response.json["created_at"] == created["created_at"]


def test_update_rejects_invalid_fields(client):
    created = client.post("/tasks", json={"title": "Valid"}).json

    assert client.put(f"/tasks/{created['id']}", json={"title": ""}).status_code == 400
    assert client.put(f"/tasks/{created['id']}", json={"status": 1}).status_code == 400
