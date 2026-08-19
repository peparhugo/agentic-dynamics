from datetime import date, timedelta

from tests.conftest import auth_header, get_token, register_user


def _create_task(client, token, **overrides):
    payload = {
        "title": "Buy groceries",
        "description": "Milk, eggs, bread",
        "status": "pending",
        "priority": "medium",
        "due_date": "2026-12-01",
    }
    payload.update(overrides)
    return client.post("/api/tasks", json=payload, headers=auth_header(token))


def test_create_task(client):
    token = get_token(client)
    resp = _create_task(client, token)
    assert resp.status_code == 201
    task = resp.get_json()["task"]
    assert task["title"] == "Buy groceries"
    assert task["status"] == "pending"
    assert task["priority"] == "medium"
    assert task["due_date"] == "2026-12-01"
    assert task["creator_id"] == 1


def test_create_task_requires_auth(client):
    resp = client.post("/api/tasks", json={"title": "No auth"})
    assert resp.status_code == 401


def test_create_task_missing_title(client):
    token = get_token(client)
    resp = client.post("/api/tasks", json={}, headers=auth_header(token))
    assert resp.status_code == 400


def test_create_task_invalid_status(client):
    token = get_token(client)
    resp = _create_task(client, token, status="bogus")
    assert resp.status_code == 400


def test_create_task_invalid_priority(client):
    token = get_token(client)
    resp = _create_task(client, token, priority="bogus")
    assert resp.status_code == 400


def test_create_task_invalid_due_date(client):
    token = get_token(client)
    resp = _create_task(client, token, due_date="01/12/2026")
    assert resp.status_code == 400


def test_create_task_with_nonexistent_category(client):
    token = get_token(client)
    resp = _create_task(client, token, category_id=999)
    assert resp.status_code == 404


def test_create_task_with_assignee(client):
    token = get_token(client)
    assignee_token = get_token(
        client, username="bob", email="bob@example.com", password="secret456"
    )
    resp = _create_task(client, token, assignee_id=2)
    assert resp.status_code == 201
    assert resp.get_json()["task"]["assignee_id"] == 2


def test_create_task_with_nonexistent_assignee(client):
    token = get_token(client)
    resp = _create_task(client, token, assignee_id=999)
    assert resp.status_code == 404


def test_get_task(client):
    token = get_token(client)
    created = _create_task(client, token).get_json()["task"]
    resp = client.get(f"/api/tasks/{created['id']}", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.get_json()["task"]["id"] == created["id"]


def test_get_task_not_found(client):
    token = get_token(client)
    resp = client.get("/api/tasks/999", headers=auth_header(token))
    assert resp.status_code == 404


def test_update_task(client):
    token = get_token(client)
    created = _create_task(client, token).get_json()["task"]
    resp = client.put(
        f"/api/tasks/{created['id']}",
        json={"title": "Updated", "status": "completed", "priority": "high"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    task = resp.get_json()["task"]
    assert task["title"] == "Updated"
    assert task["status"] == "completed"
    assert task["priority"] == "high"


def test_update_task_not_found(client):
    token = get_token(client)
    resp = client.put("/api/tasks/999", json={"title": "X"}, headers=auth_header(token))
    assert resp.status_code == 404


def test_update_task_invalid_status(client):
    token = get_token(client)
    created = _create_task(client, token).get_json()["task"]
    resp = client.put(
        f"/api/tasks/{created['id']}",
        json={"status": "nope"},
        headers=auth_header(token),
    )
    assert resp.status_code == 400


def test_delete_task(client):
    token = get_token(client)
    created = _create_task(client, token).get_json()["task"]
    resp = client.delete(f"/api/tasks/{created['id']}", headers=auth_header(token))
    assert resp.status_code == 200
    resp = client.get(f"/api/tasks/{created['id']}", headers=auth_header(token))
    assert resp.status_code == 404


def test_delete_task_not_found(client):
    token = get_token(client)
    resp = client.delete("/api/tasks/999", headers=auth_header(token))
    assert resp.status_code == 404
