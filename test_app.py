import json

import pytest

from app import create_app


@pytest.fixture
def tasks_file(tmp_path):
    return tmp_path / "tasks.json"


@pytest.fixture
def client(tasks_file):
    app = create_app({"TESTING": True, "TASKS_FILE": str(tasks_file)})
    return app.test_client()


def test_storage_is_initialized(client, tasks_file):
    assert json.loads(tasks_file.read_text()) == []


def test_create_task(client, tasks_file):
    response = client.post("/tasks", json={"title": "Write tests"})

    assert response.status_code == 201
    assert response.json["id"] == 1
    assert response.json["title"] == "Write tests"
    assert response.json["status"] == "pending"
    assert response.json["created_at"]
    assert json.loads(tasks_file.read_text())[0] == response.json


@pytest.mark.parametrize(
    "body",
    [None, {}, {"title": ""}, {"title": "   "}, {"title": 12}],
)
def test_create_requires_title(client, body):
    response = client.post("/tasks", json=body)

    assert response.status_code == 400
    assert response.json == {"error": "title is required"}


def test_list_tasks_newest_first(client):
    first = client.post("/tasks", json={"title": "First"}).json
    second = client.post("/tasks", json={"title": "Second"}).json

    response = client.get("/tasks")

    assert response.status_code == 200
    assert response.json == [second, first]


def test_get_task(client):
    created = client.post("/tasks", json={"title": "Read me"}).json

    response = client.get(f"/tasks/{created['id']}")

    assert response.status_code == 200
    assert response.json == created


def test_missing_task_returns_json_404(client):
    response = client.get("/tasks/999")

    assert response.status_code == 404
    assert response.json == {"error": "task not found"}


def test_update_title_and_status(client):
    task_id = client.post("/tasks", json={"title": "Old"}).json["id"]

    response = client.put(
        f"/tasks/{task_id}", json={"title": "New", "status": "complete"}
    )

    assert response.status_code == 200
    assert response.json["title"] == "New"
    assert response.json["status"] == "complete"
    assert client.get(f"/tasks/{task_id}").json == response.json


def test_update_one_field_preserves_the_other(client):
    task = client.post("/tasks", json={"title": "Keep"}).json

    response = client.put(f"/tasks/{task['id']}", json={"status": "done"})

    assert response.status_code == 200
    assert response.json["title"] == "Keep"
    assert response.json["status"] == "done"


@pytest.mark.parametrize(
    ("body", "error"),
    [
        (None, "JSON body is required"),
        ({}, "title or status is required"),
        ({"title": ""}, "title must be a non-empty string"),
        ({"status": None}, "status must be a non-empty string"),
    ],
)
def test_update_validates_body(client, body, error):
    task_id = client.post("/tasks", json={"title": "Task"}).json["id"]

    response = client.put(f"/tasks/{task_id}", json=body)

    assert response.status_code == 400
    assert response.json == {"error": error}


def test_update_missing_task_returns_json_404(client):
    response = client.put("/tasks/999", json={"status": "done"})

    assert response.status_code == 404
    assert response.json == {"error": "task not found"}


def test_ids_continue_after_restart(tasks_file):
    first_app = create_app({"TESTING": True, "TASKS_FILE": str(tasks_file)})
    first_app.test_client().post("/tasks", json={"title": "First"})

    second_app = create_app({"TESTING": True, "TASKS_FILE": str(tasks_file)})
    response = second_app.test_client().post("/tasks", json={"title": "Second"})

    assert response.json["id"] == 2
