import app as task_app
import pytest


@pytest.fixture
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

    response = client.get(f"/tasks/{task['id']}")
    assert response.status_code == 200
    assert response.get_json() == task


@pytest.mark.parametrize(
    "request_kwargs",
    [{"json": {}}, {"json": {"title": "  "}}, {"data": "not json"}],
)
def test_create_requires_title(client, request_kwargs):
    response = client.post("/tasks", **request_kwargs)

    assert response.status_code == 400
    assert response.get_json() == {"error": "title is required"}


def test_list_tasks_newest_first(client):
    first = client.post("/tasks", json={"title": "First"}).get_json()
    second = client.post("/tasks", json={"title": "Second"}).get_json()

    response = client.get("/tasks")

    assert response.status_code == 200
    assert [task["id"] for task in response.get_json()] == [second["id"], first["id"]]


def test_update_task(client):
    task = client.post("/tasks", json={"title": "Old"}).get_json()

    response = client.put(
        f"/tasks/{task['id']}", json={"title": "New", "status": "done"}
    )

    assert response.status_code == 200
    assert response.get_json()["title"] == "New"
    assert response.get_json()["status"] == "done"


@pytest.mark.parametrize("method", ["get", "put"])
def test_missing_task_returns_404(client, method):
    kwargs = {"json": {"status": "done"}} if method == "put" else {}
    response = getattr(client, method)("/tasks/999", **kwargs)

    assert response.status_code == 404
    assert response.get_json() == {"error": "task not found"}
