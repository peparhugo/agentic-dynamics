def _create(client, headers, **overrides):
    payload = {"title": "Buy groceries", "description": "Milk and eggs"}
    payload.update(overrides)
    return client.post("/tasks", json=payload, headers=headers)


def test_create_task(client, auth_headers):
    headers, _ = auth_headers
    resp = _create(client, headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Buy groceries"
    assert data["status"] == "pending"
    assert data["priority"] == "medium"
    assert data["creator_id"] is not None


def test_create_task_requires_title(client, auth_headers):
    headers, _ = auth_headers
    resp = client.post("/tasks", json={"description": "no title"}, headers=headers)
    assert resp.status_code == 400


def test_create_task_invalid_status(client, auth_headers):
    headers, _ = auth_headers
    resp = _create(client, headers, status="bogus")
    assert resp.status_code == 400


def test_create_task_invalid_priority(client, auth_headers):
    headers, _ = auth_headers
    resp = _create(client, headers, priority="bogus")
    assert resp.status_code == 400


def test_create_task_invalid_due_date(client, auth_headers):
    headers, _ = auth_headers
    resp = _create(client, headers, due_date="not-a-date")
    assert resp.status_code == 400


def test_create_task_with_due_date(client, auth_headers):
    headers, _ = auth_headers
    resp = _create(client, headers, due_date="2026-12-31")
    assert resp.status_code == 201
    assert resp.get_json()["due_date"] == "2026-12-31"


def test_create_task_assignee_not_found(client, auth_headers):
    headers, _ = auth_headers
    resp = _create(client, headers, assignee_id=999)
    assert resp.status_code == 404


def test_get_task(client, auth_headers):
    headers, _ = auth_headers
    task_id = _create(client, headers).get_json()["id"]
    resp = client.get(f"/tasks/{task_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["id"] == task_id


def test_get_task_not_found(client, auth_headers):
    headers, _ = auth_headers
    resp = client.get("/tasks/9999", headers=headers)
    assert resp.status_code == 404


def test_update_task(client, auth_headers):
    headers, _ = auth_headers
    task_id = _create(client, headers).get_json()["id"]
    resp = client.put(
        f"/tasks/{task_id}",
        json={"title": "Updated", "status": "completed", "priority": "high"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Updated"
    assert data["status"] == "completed"
    assert data["priority"] == "high"


def test_update_task_not_found(client, auth_headers):
    headers, _ = auth_headers
    resp = client.put("/tasks/9999", json={"title": "x"}, headers=headers)
    assert resp.status_code == 404


def test_delete_task(client, auth_headers):
    headers, _ = auth_headers
    task_id = _create(client, headers).get_json()["id"]
    resp = client.delete(f"/tasks/{task_id}", headers=headers)
    assert resp.status_code == 200
    assert client.get(f"/tasks/{task_id}", headers=headers).status_code == 404


def test_delete_task_not_found(client, auth_headers):
    headers, _ = auth_headers
    resp = client.delete("/tasks/9999", headers=headers)
    assert resp.status_code == 404


def test_assign_task(client, auth_headers, second_user):
    headers, _ = auth_headers
    task_id = _create(client, headers).get_json()["id"]
    resp = client.post(
        f"/tasks/{task_id}/assign",
        json={"assignee_id": second_user["id"]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["assignee_id"] == second_user["id"]


def test_assign_task_missing_id(client, auth_headers):
    headers, _ = auth_headers
    task_id = _create(client, headers).get_json()["id"]
    resp = client.post(f"/tasks/{task_id}/assign", json={}, headers=headers)
    assert resp.status_code == 400


def test_tasks_require_auth(client):
    resp = client.get("/tasks")
    assert resp.status_code == 401
