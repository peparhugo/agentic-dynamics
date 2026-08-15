import pytest

from app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    storage_file = tmp_path / "tasks.json"
    monkeypatch.setenv("TASKS_FILE", str(storage_file))
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def create(client, title="Buy milk"):
    return client.post("/tasks", json={"title": title})


def test_create_task_success(client):
    resp = create(client, "Write report")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["id"] == 1
    assert body["title"] == "Write report"
    assert body["status"] == "pending"
    assert "created_at" in body


def test_create_task_missing_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_empty_title(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_non_string_title(client):
    resp = client.post("/tasks", json={"title": 123})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_no_body(client):
    resp = client.post("/tasks")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_empty(client):
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_tasks_ordered_desc(client):
    create(client, "first")
    create(client, "second")
    create(client, "third")

    resp = client.get("/tasks")
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["third", "second", "first"]


def test_get_task_success(client):
    created = create(client, "Read book").get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json() == created


def test_get_task_not_found(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client):
    created = create(client, "old title").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "new title"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "new title"
    assert body["status"] == "pending"


def test_update_task_status(client):
    created = create(client, "task").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "done"
    assert body["title"] == "task"


def test_update_task_title_and_status(client):
    created = create(client, "task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "updated", "status": "in_progress"}
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "updated"
    assert body["status"] == "in_progress"


def test_update_task_not_found(client):
    resp = client.put("/tasks/999", json={"title": "x"})
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_no_fields(client):
    created = create(client, "task").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_update_task_empty_title(client):
    created = create(client, "task").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "  "})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_data_persisted_to_flat_file(client, tmp_path):
    create(client, "persisted task")
    storage_file = tmp_path / "tasks.json"
    assert storage_file.exists()
    contents = storage_file.read_text()
    assert "persisted task" in contents
