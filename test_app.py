import pytest

import app as app_module


@pytest.fixture
def client(tmp_path):
    app_module.DATABASE = str(tmp_path / "test.db")
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client


def test_create_task(client):
    resp = client.post("/tasks", json={"title": "Buy milk"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert isinstance(data["id"], int)
    assert "created_at" in data


def test_create_task_missing_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_blank_title(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_task_no_body(client):
    resp = client.post("/tasks")
    assert resp.status_code == 400


def test_list_tasks_empty(client):
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_tasks_ordered_desc(client):
    client.post("/tasks", json={"title": "first"})
    client.post("/tasks", json={"title": "second"})
    resp = client.get("/tasks")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2
    assert data[0]["title"] == "second"
    assert data[1]["title"] == "first"


def test_get_task(client):
    created = client.post("/tasks", json={"title": "task"}).get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == created["id"]
    assert data["title"] == "task"
    assert data["status"] == "pending"


def test_get_task_not_found(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client):
    created = client.post("/tasks", json={"title": "old"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "new"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "new"
    assert data["status"] == "pending"


def test_update_task_status(client):
    created = client.post("/tasks", json={"title": "task"}).get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "done"
    assert data["title"] == "task"


def test_update_task_title_and_status(client):
    created = client.post("/tasks", json={"title": "task"}).get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "renamed", "status": "done"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "renamed"
    assert data["status"] == "done"


def test_update_task_not_found(client):
    resp = client.put("/tasks/999", json={"title": "x"})
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_ids_assigned_manually_incrementing(client):
    t1 = client.post("/tasks", json={"title": "a"}).get_json()
    t2 = client.post("/tasks", json={"title": "b"}).get_json()
    assert t2["id"] == t1["id"] + 1
