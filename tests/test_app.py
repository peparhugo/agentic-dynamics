import json

import pytest

import app as app_module


@pytest.fixture
def client(tmp_path):
    app_module.app.config["STORAGE_FILE"] = str(tmp_path / "tasks.json")
    app_module.app.config["TESTING"] = True
    app_module.init_storage()
    return app_module.app.test_client()


@pytest.fixture
def storage_file():
    return app_module.app.config["STORAGE_FILE"]


def _create(client, title):
    return client.post("/tasks", json={"title": title})


def test_create_task(client):
    resp = _create(client, "Write report")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["title"] == "Write report"
    assert data["status"] == "pending"
    assert data["created_at"]


def test_create_task_returns_400_when_title_missing(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_returns_400_when_title_empty(client):
    resp = client.post("/tasks", json={"title": ""})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_ordered_by_created_at_desc(client):
    _create(client, "First")
    _create(client, "Second")
    resp = client.get("/tasks")
    assert resp.status_code == 200
    tasks = resp.get_json()
    assert [t["title"] for t in tasks] == ["Second", "First"]
    assert [t["created_at"] for t in tasks] == sorted(
        [t["created_at"] for t in tasks], reverse=True
    )


def test_get_task(client):
    created = _create(client, "Buy milk").get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json() == created


def test_get_task_returns_404_when_not_found(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client):
    created = _create(client, "Old title").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "New title"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status(client):
    created = _create(client, "Do it").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "done"
    assert data["title"] == "Do it"


def test_update_task_title_and_status(client):
    created = _create(client, "A").get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "B", "status": "in_progress"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "B"
    assert data["status"] == "in_progress"


def test_update_task_returns_404_when_not_found(client):
    resp = client.put("/tasks/999", json={"title": "X"})
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_returns_400_when_title_emptied(client):
    created = _create(client, "A").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": ""})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_data_stored_in_flat_file(client, storage_file):
    _create(client, "Persist me")
    with open(storage_file) as f:
        stored = json.load(f)
    assert isinstance(stored, list)
    assert stored[0]["title"] == "Persist me"
    assert stored[0]["id"] == 1


def test_data_persists_across_requests(client, storage_file):
    _create(client, "One")
    _create(client, "Two")
    tasks = client.get("/tasks").get_json()
    assert [t["title"] for t in tasks] == ["Two", "One"]


def test_no_sqlite_database_file_created(client, tmp_path):
    _create(client, "No db")
    assert list(tmp_path.iterdir()) == [tmp_path / "tasks.json"]
