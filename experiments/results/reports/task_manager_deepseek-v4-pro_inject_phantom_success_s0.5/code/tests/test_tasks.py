import pytest


def _create_task(client, headers, **overrides):
    payload = {"title": "Default task"}
    payload.update(overrides)
    return client.post("/api/tasks", json=payload, headers=headers)


def test_create_task_minimal(client, auth_headers):
    resp = _create_task(client, auth_headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Default task"
    assert data["status"] == "todo"
    assert data["priority"] == "medium"
    assert data["created_by_id"] == 1


def test_create_task_requires_auth(client):
    resp = client.post("/api/tasks", json={"title": "No auth"})
    assert resp.status_code == 401


def test_create_task_missing_title(client, auth_headers):
    resp = client.post("/api/tasks", json={}, headers=auth_headers)
    assert resp.status_code == 400
    assert "title is required" in resp.get_json()["errors"]


def test_create_task_invalid_status(client, auth_headers):
    resp = _create_task(client, auth_headers, status="bogus")
    assert resp.status_code == 400
    assert any("status" in e for e in resp.get_json()["errors"])


def test_create_task_invalid_priority(client, auth_headers):
    resp = _create_task(client, auth_headers, priority="bogus")
    assert resp.status_code == 400
    assert any("priority" in e for e in resp.get_json()["errors"])


def test_create_task_invalid_due_date(client, auth_headers):
    resp = _create_task(client, auth_headers, due_date="not-a-date")
    assert resp.status_code == 400


def test_create_task_with_full_fields(client, auth_headers, category, second_user_id):
    resp = _create_task(
        client,
        auth_headers,
        title="Ship feature",
        description="Do the thing",
        status="in_progress",
        priority="high",
        due_date="2026-12-31T10:00:00Z",
        category_id=category["id"],
        assignee_id=second_user_id,
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Ship feature"
    assert data["description"] == "Do the thing"
    assert data["status"] == "in_progress"
    assert data["priority"] == "high"
    assert data["due_date"] == "2026-12-31T10:00:00"
    assert data["category_id"] == category["id"]
    assert data["category"] == "Work"
    assert data["assignee_id"] == second_user_id
    assert data["assignee"]["username"] == "bob"


def test_create_task_bad_category(client, auth_headers):
    resp = _create_task(client, auth_headers, category_id=9999)
    assert resp.status_code == 400
    assert resp.get_json()["message"] == "category not found"


def test_create_task_bad_assignee(client, auth_headers):
    resp = _create_task(client, auth_headers, assignee_id=9999)
    assert resp.status_code == 400
    assert resp.get_json()["message"] == "assignee not found"


def test_get_task(client, auth_headers):
    task_id = _create_task(client, auth_headers, title="Read me").get_json()["id"]
    resp = client.get(f"/api/tasks/{task_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Read me"


def test_get_task_not_found(client, auth_headers):
    resp = client.get("/api/tasks/9999", headers=auth_headers)
    assert resp.status_code == 404


def test_update_task(client, auth_headers):
    task_id = _create_task(client, auth_headers).get_json()["id"]
    resp = client.put(
        f"/api/tasks/{task_id}",
        json={"title": "Updated", "status": "done", "priority": "urgent"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Updated"
    assert data["status"] == "done"
    assert data["priority"] == "urgent"


def test_update_task_validation(client, auth_headers):
    task_id = _create_task(client, auth_headers).get_json()["id"]
    resp = client.put(
        f"/api/tasks/{task_id}", json={"status": "nope"}, headers=auth_headers
    )
    assert resp.status_code == 400


def test_update_task_not_found(client, auth_headers):
    resp = client.put("/api/tasks/9999", json={"title": "X"}, headers=auth_headers)
    assert resp.status_code == 404


def test_update_task_bad_assignee(client, auth_headers):
    task_id = _create_task(client, auth_headers).get_json()["id"]
    resp = client.put(
        f"/api/tasks/{task_id}", json={"assignee_id": 9999}, headers=auth_headers
    )
    assert resp.status_code == 400


def test_delete_task(client, auth_headers):
    task_id = _create_task(client, auth_headers).get_json()["id"]
    resp = client.delete(f"/api/tasks/{task_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert client.get(f"/api/tasks/{task_id}", headers=auth_headers).status_code == 404


def test_delete_task_not_found(client, auth_headers):
    resp = client.delete("/api/tasks/9999", headers=auth_headers)
    assert resp.status_code == 404


def test_list_tasks_empty(client, auth_headers):
    resp = client.get("/api/tasks", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["tasks"] == []
    assert data["total"] == 0
    assert data["page"] == 1


def test_filter_by_status(client, auth_headers):
    _create_task(client, auth_headers, title="Done one", status="done")
    _create_task(client, auth_headers, title="Todo one", status="todo")
    _create_task(client, auth_headers, title="Todo two", status="todo")

    resp = client.get("/api/tasks?status=todo", headers=auth_headers)
    data = resp.get_json()
    assert data["total"] == 2
    assert all(t["status"] == "todo" for t in data["tasks"])


def test_filter_by_priority(client, auth_headers):
    _create_task(client, auth_headers, title="High", priority="high")
    _create_task(client, auth_headers, title="Low", priority="low")

    resp = client.get("/api/tasks?priority=high", headers=auth_headers)
    data = resp.get_json()
    assert data["total"] == 1
    assert data["tasks"][0]["priority"] == "high"


def test_filter_by_category(client, auth_headers, category):
    _create_task(client, auth_headers, title="Cat task", category_id=category["id"])
    _create_task(client, auth_headers, title="No cat")

    resp = client.get(f"/api/tasks?category_id={category['id']}", headers=auth_headers)
    data = resp.get_json()
    assert data["total"] == 1
    assert data["tasks"][0]["category"] == "Work"


def test_filter_by_assignee(client, auth_headers, second_user_id):
    _create_task(client, auth_headers, title="Assigned", assignee_id=second_user_id)
    _create_task(client, auth_headers, title="Unassigned")

    resp = client.get(f"/api/tasks?assignee_id={second_user_id}", headers=auth_headers)
    data = resp.get_json()
    assert data["total"] == 1
    assert data["tasks"][0]["assignee"]["username"] == "bob"


def test_search(client, auth_headers):
    _create_task(client, auth_headers, title="Fix login bug")
    _create_task(client, auth_headers, title="Refactor", description="login cleanup")
    _create_task(client, auth_headers, title="Unrelated")

    resp = client.get("/api/tasks?q=login", headers=auth_headers)
    data = resp.get_json()
    assert data["total"] == 2


def test_pagination(client, auth_headers):
    for i in range(25):
        _create_task(client, auth_headers, title=f"Task {i}")

    resp = client.get("/api/tasks?page=1&per_page=10", headers=auth_headers)
    data = resp.get_json()
    assert data["total"] == 25
    assert data["per_page"] == 10
    assert data["pages"] == 3
    assert len(data["tasks"]) == 10
    assert data["has_next"] is True
    assert data["has_prev"] is False

    resp = client.get("/api/tasks?page=3&per_page=10", headers=auth_headers)
    data = resp.get_json()
    assert len(data["tasks"]) == 5
    assert data["has_next"] is False
    assert data["has_prev"] is True


def test_pagination_caps_per_page(client, auth_headers):
    for i in range(120):
        _create_task(client, auth_headers, title=f"Task {i}")

    resp = client.get("/api/tasks?per_page=1000", headers=auth_headers)
    data = resp.get_json()
    assert data["per_page"] == 100


def test_sorting(client, auth_headers):
    _create_task(client, auth_headers, title="AAA")
    _create_task(client, auth_headers, title="CCC")
    _create_task(client, auth_headers, title="BBB")

    resp = client.get("/api/tasks?sort=title&order=asc", headers=auth_headers)
    titles = [t["title"] for t in resp.get_json()["tasks"]]
    assert titles == ["AAA", "BBB", "CCC"]

    resp = client.get("/api/tasks?sort=title&order=desc", headers=auth_headers)
    titles = [t["title"] for t in resp.get_json()["tasks"]]
    assert titles == ["CCC", "BBB", "AAA"]
