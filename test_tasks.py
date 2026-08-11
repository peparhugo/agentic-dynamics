import pytest
from app import app, init_db, get_db


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.app_context():
        init_db()
        with get_db() as conn:
            conn.execute("DELETE FROM tasks")
            conn.commit()
    with app.test_client() as client:
        yield client


def test_create_task_success(client):
    res = client.post("/tasks", json={"title": "Buy groceries"})
    assert res.status_code == 201
    data = res.get_json()
    assert data["title"] == "Buy groceries"
    assert data["status"] == "pending"
    assert data["id"] is not None
    assert "created_at" in data


def test_create_task_missing_title_returns_400(client):
    res = client.post("/tasks", json={})
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_create_task_empty_title_returns_400(client):
    res = client.post("/tasks", json={"title": ""})
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_create_task_whitespace_title_returns_400(client):
    res = client.post("/tasks", json={"title": "   "})
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_list_tasks_empty(client):
    res = client.get("/tasks")
    assert res.status_code == 200
    assert res.get_json() == []


def test_list_tasks_ordered_by_created_at_desc(client):
    client.post("/tasks", json={"title": "First"})
    client.post("/tasks", json={"title": "Second"})
    res = client.get("/tasks")
    data = res.get_json()
    assert len(data) == 2
    assert data[0]["title"] == "Second"
    assert data[1]["title"] == "First"


def test_get_task_success(client):
    create_res = client.post("/tasks", json={"title": "Test task"})
    task_id = create_res.get_json()["id"]
    res = client.get(f"/tasks/{task_id}")
    assert res.status_code == 200
    assert res.get_json()["title"] == "Test task"


def test_get_task_not_found(client):
    res = client.get("/tasks/9999")
    assert res.status_code == 404
    assert "error" in res.get_json()


def test_update_task_title(client):
    create_res = client.post("/tasks", json={"title": "Original"})
    task_id = create_res.get_json()["id"]
    res = client.put(f"/tasks/{task_id}", json={"title": "Updated"})
    assert res.status_code == 200
    assert res.get_json()["title"] == "Updated"
    assert res.get_json()["status"] == "pending"


def test_update_task_status(client):
    create_res = client.post("/tasks", json={"title": "Task"})
    task_id = create_res.get_json()["id"]
    res = client.put(f"/tasks/{task_id}", json={"status": "completed"})
    assert res.status_code == 200
    assert res.get_json()["status"] == "completed"
    assert res.get_json()["title"] == "Task"


def test_update_task_both_fields(client):
    create_res = client.post("/tasks", json={"title": "Old"})
    task_id = create_res.get_json()["id"]
    res = client.put(f"/tasks/{task_id}", json={"title": "New", "status": "done"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["title"] == "New"
    assert data["status"] == "done"


def test_update_task_empty_title_returns_400(client):
    create_res = client.post("/tasks", json={"title": "Task"})
    task_id = create_res.get_json()["id"]
    res = client.put(f"/tasks/{task_id}", json={"title": ""})
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_update_task_whitespace_title_returns_400(client):
    create_res = client.post("/tasks", json={"title": "Task"})
    task_id = create_res.get_json()["id"]
    res = client.put(f"/tasks/{task_id}", json={"title": "   "})
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_update_task_not_found(client):
    res = client.put("/tasks/9999", json={"title": "Ghost"})
    assert res.status_code == 404
    assert "error" in res.get_json()


def test_update_task_with_no_fields_does_not_crash(client):
    create_res = client.post("/tasks", json={"title": "Keep"})
    task_id = create_res.get_json()["id"]
    res = client.put(f"/tasks/{task_id}", json={})
    assert res.status_code == 200
    data = res.get_json()
    assert data["title"] == "Keep"
    assert data["status"] == "pending"


def test_task_default_status_is_pending(client):
    res = client.post("/tasks", json={"title": "Default test"})
    assert res.get_json()["status"] == "pending"
