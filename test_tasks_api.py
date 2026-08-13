import os
import time

import pytest

from tasks_api import create_app


@pytest.fixture
def client(tmp_path):
    db_path = os.path.join(tmp_path, "test_tasks.db")
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def create_task(client, title):
    return client.post("/tasks", json={"title": title})


def test_create_task_success(client):
    resp = create_task(client, "Buy milk")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["id"] == 1
    assert body["title"] == "Buy milk"
    assert body["status"] == "pending"
    assert "created_at" in body


def test_create_task_missing_title(client):
    resp = client.post("/tasks", json={})
    assert resp.status_code == 400
    body = resp.get_json()
    assert "error" in body


def test_create_task_blank_title(client):
    resp = client.post("/tasks", json={"title": "   "})
    assert resp.status_code == 400


def test_create_task_no_body(client):
    resp = client.post("/tasks")
    assert resp.status_code == 400


def test_ids_increment_manually(client):
    r1 = create_task(client, "Task 1").get_json()
    r2 = create_task(client, "Task 2").get_json()
    r3 = create_task(client, "Task 3").get_json()
    assert [r1["id"], r2["id"], r3["id"]] == [1, 2, 3]


def test_list_tasks_empty(client):
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_tasks_ordered_desc(client):
    create_task(client, "First")
    time.sleep(0.01)
    create_task(client, "Second")
    time.sleep(0.01)
    create_task(client, "Third")

    resp = client.get("/tasks")
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.get_json()]
    assert titles == ["Third", "Second", "First"]


def test_get_task_success(client):
    created = create_task(client, "Read book").get_json()
    resp = client.get(f"/tasks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Read book"


def test_get_task_not_found(client):
    resp = client.get("/tasks/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_title(client):
    created = create_task(client, "Old title").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "New title"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "New title"
    assert body["status"] == "pending"


def test_update_task_status(client):
    created = create_task(client, "Task").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"status": "done"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "done"
    assert body["title"] == "Task"


def test_update_task_title_and_status(client):
    created = create_task(client, "Task").get_json()
    resp = client.put(
        f"/tasks/{created['id']}", json={"title": "Updated", "status": "in_progress"}
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "Updated"
    assert body["status"] == "in_progress"


def test_update_task_not_found(client):
    resp = client.put("/tasks/999", json={"title": "Nope"})
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_update_task_no_fields(client):
    created = create_task(client, "Task").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={})
    assert resp.status_code == 400


def test_update_task_blank_title(client):
    created = create_task(client, "Task").get_json()
    resp = client.put(f"/tasks/{created['id']}", json={"title": "  "})
    assert resp.status_code == 400


def test_full_response_is_json(client):
    resp = create_task(client, "JSON check")
    assert resp.content_type == "application/json"
    resp = client.get("/tasks/999")
    assert resp.content_type == "application/json"
