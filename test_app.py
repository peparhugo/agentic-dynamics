import pytest
import app as app_module


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def clear_db():
    conn = app_module.get_db()
    conn.execute("DELETE FROM tasks")
    conn.commit()
    conn.close()
    yield


def test_create_task(client):
    resp = client.post("/tasks", json={"title": "Buy groceries"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy groceries"
    assert data["status"] == "pending"
    assert "id" in data
    assert "created_at" in data


def test_create_task_default_status(client):
    resp = client.post("/tasks", json={"title": "Do laundry"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["status"] == "pending"


def test_create_task_missing_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_empty_title(client):
    resp = client.post("/tasks", json={"title": ""})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_no_json(client):
    resp = client.post("/tasks", data="not json", content_type="text/plain")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_list_tasks_empty(client):
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_tasks_with_data(client):
    client.post("/tasks", json={"title": "Task 1"})
    client.post("/tasks", json={"title": "Task 2"})
    resp = client.get("/tasks")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2
    assert data[0]["title"] == "Task 2"
    assert data[1]["title"] == "Task 1"


def test_get_task_found(client):
    r = client.post("/tasks", json={"title": "Find me"})
    task_id = r.get_json()["id"]
    resp = client.get(f"/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Find me"


def test_get_task_not_found(client):
    resp = client.get("/tasks/9999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client):
    r = client.post("/tasks", json={"title": "Old title"})
    task_id = r.get_json()["id"]
    resp = client.put(f"/tasks/{task_id}", json={"title": "New title"})
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "New title"
    assert resp.get_json()["status"] == "pending"


def test_update_task_status(client):
    r = client.post("/tasks", json={"title": "Task"})
    task_id = r.get_json()["id"]
    resp = client.put(f"/tasks/{task_id}", json={"status": "completed"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
    assert resp.get_json()["title"] == "Task"


def test_update_task_both(client):
    r = client.post("/tasks", json={"title": "Task"})
    task_id = r.get_json()["id"]
    resp = client.put(
        f"/tasks/{task_id}",
        json={"title": "Done", "status": "completed"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Done"
    assert data["status"] == "completed"


def test_update_task_not_found(client):
    resp = client.put("/tasks/9999", json={"title": "Nope"})
    assert resp.status_code == 404
    assert "error" in resp.get_json()
