import pytest

from conftest import auth_headers, create_task


def test_create_task_minimal(client, users):
    resp = create_task(client, users["alice"]["token"], title="Buy milk")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy milk"
    assert data["status"] == "pending"
    assert data["description"] == ""
    assert data["priority"] is None
    assert data["category"] is None
    assert data["due_date"] is None
    assert data["assignee"] is None
    assert data["creator"]["username"] == "alice"
    assert data["id"]


def test_create_task_full(client, users, priority_ids, category_ids):
    resp = create_task(
        client,
        users["alice"]["token"],
        title="Ship feature",
        description="Finish the API",
        status="in_progress",
        priority_id=priority_ids["high"],
        category_id=category_ids["Work"],
        due_date="2026-12-31",
        assignee_id=users["bob"]["id"],
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["priority"]["name"] == "high"
    assert data["category"]["name"] == "Work"
    assert data["due_date"] == "2026-12-31"
    assert data["assignee"]["username"] == "bob"


def test_create_task_by_priority_name_and_category_name(client, users, priority_ids, category_ids):
    resp = create_task(
        client,
        users["alice"]["token"],
        title="Named refs",
        priority="urgent",
        category="Personal",
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["priority"]["name"] == "urgent"
    assert data["category"]["name"] == "Personal"


def test_create_task_requires_title(client, users):
    resp = create_task(client, users["alice"]["token"], title="   ")
    assert resp.status_code == 400
    resp = client.post("/tasks", json={}, headers=auth_headers(users["alice"]["token"]))
    assert resp.status_code == 400


def test_create_task_invalid_status(client, users):
    resp = create_task(client, users["alice"]["token"], title="Bad", status="done_soon")
    assert resp.status_code == 400


def test_create_task_unknown_priority(client, users):
    resp = create_task(client, users["alice"]["token"], title="Bad prio", priority="super")
    assert resp.status_code == 400


def test_create_task_unknown_category(client, users):
    resp = create_task(client, users["alice"]["token"], title="Bad cat", category="Nope")
    assert resp.status_code == 400


def test_create_task_invalid_due_date(client, users):
    resp = create_task(client, users["alice"]["token"], title="Bad date", due_date="not-a-date")
    assert resp.status_code == 400


def test_create_task_unknown_assignee(client, users):
    resp = create_task(client, users["alice"]["token"], title="Bad assign", assignee_id=9999)
    assert resp.status_code == 400


def test_create_task_requires_auth(client):
    resp = client.post("/tasks", json={"title": "nope"})
    assert resp.status_code == 401


def test_get_task(client, users):
    created = create_task(client, users["alice"]["token"], title="Lookup me")
    task_id = created.get_json()["id"]
    resp = client.get(f"/tasks/{task_id}", headers=auth_headers(users["bob"]["token"]))
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Lookup me"


def test_get_task_not_found(client, users):
    resp = client.get("/tasks/9999", headers=auth_headers(users["alice"]["token"]))
    assert resp.status_code == 404


def test_update_task_partial(client, users):
    created = create_task(client, users["alice"]["token"], title="Old title")
    task_id = created.get_json()["id"]
    resp = client.put(
        f"/tasks/{task_id}", json={"title": "New title"}, headers=auth_headers(users["alice"]["token"])
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "New title"
    assert data["status"] == "pending"


def test_update_task_status_and_dates(client, users):
    created = create_task(client, users["alice"]["token"], title="Workflow")
    task_id = created.get_json()["id"]
    resp = client.put(
        f"/tasks/{task_id}",
        json={"status": "completed", "due_date": "2026-08-20"},
        headers=auth_headers(users["alice"]["token"]),
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "completed"
    assert data["due_date"] == "2026-08-20"


def test_update_task_empty_payload(client, users):
    created = create_task(client, users["alice"]["token"], title="Static")
    task_id = created.get_json()["id"]
    resp = client.put(f"/tasks/{task_id}", json={}, headers=auth_headers(users["alice"]["token"]))
    assert resp.status_code == 400


def test_update_task_not_found(client, users):
    resp = client.put(
        "/tasks/9999", json={"title": "x"}, headers=auth_headers(users["alice"]["token"])
    )
    assert resp.status_code == 404


def test_delete_task_by_creator(client, users):
    created = create_task(client, users["alice"]["token"], title="Disposable")
    task_id = created.get_json()["id"]
    resp = client.delete(f"/tasks/{task_id}", headers=auth_headers(users["alice"]["token"]))
    assert resp.status_code == 200
    resp = client.get(f"/tasks/{task_id}", headers=auth_headers(users["alice"]["token"]))
    assert resp.status_code == 404


def test_delete_task_not_found(client, users):
    resp = client.delete("/tasks/9999", headers=auth_headers(users["alice"]["token"]))
    assert resp.status_code == 404


def test_assign_task_by_username(client, users):
    created = create_task(client, users["alice"]["token"], title="Assign me")
    task_id = created.get_json()["id"]
    resp = client.post(
        f"/tasks/{task_id}/assign",
        json={"username": "carol"},
        headers=auth_headers(users["alice"]["token"]),
    )
    assert resp.status_code == 200
    assert resp.get_json()["assignee"]["username"] == "carol"


def test_assign_task_by_id(client, users):
    created = create_task(client, users["alice"]["token"], title="Assign me 2")
    task_id = created.get_json()["id"]
    resp = client.post(
        f"/tasks/{task_id}/assign",
        json={"assignee_id": users["bob"]["id"]},
        headers=auth_headers(users["alice"]["token"]),
    )
    assert resp.status_code == 200
    assert resp.get_json()["assignee"]["username"] == "bob"


def test_assign_task_requires_target(client, users):
    created = create_task(client, users["alice"]["token"], title="No assign")
    task_id = created.get_json()["id"]
    resp = client.post(
        f"/tasks/{task_id}/assign", json={}, headers=auth_headers(users["alice"]["token"])
    )
    assert resp.status_code == 400


def test_assign_task_unknown_user(client, users):
    created = create_task(client, users["alice"]["token"], title="Ghost assign")
    task_id = created.get_json()["id"]
    resp = client.post(
        f"/tasks/{task_id}/assign",
        json={"username": "ghost"},
        headers=auth_headers(users["alice"]["token"]),
    )
    assert resp.status_code == 404


def test_assign_task_not_found(client, users):
    resp = client.post(
        "/tasks/9999/assign",
        json={"username": "bob"},
        headers=auth_headers(users["alice"]["token"]),
    )
    assert resp.status_code == 404
