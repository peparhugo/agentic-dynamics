def test_create_task(client, auth_headers):
    resp = client.post(
        "/api/tasks",
        json={"title": "Write tests", "description": "do it"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["title"] == "Write tests"
    assert body["status"] == "todo"
    assert body["priority"] == "medium"
    assert body["creator_id"] is not None
    assert body["assignee_id"] is None
    assert body["category_id"] is None


def test_create_task_with_all_fields(client, auth_headers, category_id, other_user_headers):
    client.post(
        "/api/auth/register",
        json={"username": "bob2", "email": "bob2@example.com", "password": "secret123"},
    )
    resp = client.post(
        "/api/tasks",
        json={
            "title": "Full task",
            "description": "desc",
            "status": "in_progress",
            "priority": "high",
            "due_date": "2026-09-01T10:00:00+00:00",
            "category_id": category_id,
            "assignee_id": 1,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["status"] == "in_progress"
    assert body["priority"] == "high"
    assert body["due_date"] is not None
    assert body["category_id"] == category_id
    assert body["assignee_id"] == 1


def test_create_task_missing_title(client, auth_headers):
    resp = client.post("/api/tasks", json={"description": "no title"}, headers=auth_headers)
    assert resp.status_code == 400


def test_create_task_invalid_status(client, auth_headers):
    resp = client.post(
        "/api/tasks", json={"title": "x", "status": "bogus"}, headers=auth_headers
    )
    assert resp.status_code == 400


def test_create_task_invalid_priority(client, auth_headers):
    resp = client.post(
        "/api/tasks", json={"title": "x", "priority": "bogus"}, headers=auth_headers
    )
    assert resp.status_code == 400


def test_create_task_invalid_due_date(client, auth_headers):
    resp = client.post(
        "/api/tasks", json={"title": "x", "due_date": "not-a-date"}, headers=auth_headers
    )
    assert resp.status_code == 400


def test_create_task_nonexistent_category(client, auth_headers):
    resp = client.post(
        "/api/tasks", json={"title": "x", "category_id": 9999}, headers=auth_headers
    )
    assert resp.status_code == 404


def test_create_task_nonexistent_assignee(client, auth_headers):
    resp = client.post(
        "/api/tasks", json={"title": "x", "assignee_id": 9999}, headers=auth_headers
    )
    assert resp.status_code == 404


def test_get_task(client, auth_headers):
    created = client.post(
        "/api/tasks", json={"title": "Read a book"}, headers=auth_headers
    ).get_json()
    resp = client.get(f"/api/tasks/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Read a book"


def test_get_task_not_found(client, auth_headers):
    resp = client.get("/api/tasks/9999", headers=auth_headers)
    assert resp.status_code == 404


def test_update_task(client, auth_headers):
    created = client.post(
        "/api/tasks", json={"title": "Old title"}, headers=auth_headers
    ).get_json()
    resp = client.put(
        f"/api/tasks/{created['id']}",
        json={"title": "New title", "status": "done", "priority": "urgent"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "New title"
    assert body["status"] == "done"
    assert body["priority"] == "urgent"


def test_update_task_invalid_status(client, auth_headers):
    created = client.post(
        "/api/tasks", json={"title": "x"}, headers=auth_headers
    ).get_json()
    resp = client.put(
        f"/api/tasks/{created['id']}", json={"status": "bogus"}, headers=auth_headers
    )
    assert resp.status_code == 400


def test_update_task_empty_title(client, auth_headers):
    created = client.post(
        "/api/tasks", json={"title": "x"}, headers=auth_headers
    ).get_json()
    resp = client.put(
        f"/api/tasks/{created['id']}", json={"title": ""}, headers=auth_headers
    )
    assert resp.status_code == 400


def test_update_task_not_found(client, auth_headers):
    resp = client.put("/api/tasks/9999", json={"title": "x"}, headers=auth_headers)
    assert resp.status_code == 404


def test_delete_task(client, auth_headers):
    created = client.post(
        "/api/tasks", json={"title": "To delete"}, headers=auth_headers
    ).get_json()
    resp = client.delete(f"/api/tasks/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    resp2 = client.get(f"/api/tasks/{created['id']}", headers=auth_headers)
    assert resp2.status_code == 404


def test_delete_task_not_found(client, auth_headers):
    resp = client.delete("/api/tasks/9999", headers=auth_headers)
    assert resp.status_code == 404


def test_list_tasks_empty(client, auth_headers):
    resp = client.get("/api/tasks", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["tasks"] == []
    assert body["total"] == 0
    assert body["pages"] == 0


def test_task_requires_auth(client):
    resp = client.post("/api/tasks", json={"title": "x"})
    assert resp.status_code == 401
    resp = client.get("/api/tasks/1")
    assert resp.status_code == 401
    resp = client.delete("/api/tasks/1")
    assert resp.status_code == 401
