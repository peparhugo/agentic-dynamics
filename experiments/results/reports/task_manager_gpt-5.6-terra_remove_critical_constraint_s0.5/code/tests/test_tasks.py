from app.db import migrate


def create_task(client, **overrides):
    payload = {"title": "Write tests", **overrides}
    response = client.post("/tasks", json=payload)
    assert response.status_code == 201
    return response.get_json()


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_create_task_with_defaults(client):
    response = client.post("/tasks", json={"title": "  Write tests  "})
    task = response.get_json()
    assert response.status_code == 201
    assert task["id"] == 1
    assert task["title"] == "Write tests"
    assert task["description"] is None
    assert task["status"] == "pending"
    assert task["due_date"] is None
    assert task["created_at"].endswith("Z")
    assert task["updated_at"] == task["created_at"]


def test_create_task_with_all_fields(client):
    task = create_task(client, description="API coverage", status="in_progress", due_date="2026-12-31")
    assert task["description"] == "API coverage"
    assert task["status"] == "in_progress"
    assert task["due_date"] == "2026-12-31"


def test_create_rejects_invalid_bodies(client):
    cases = [
        ({}, "title is required"),
        ({"title": "   "}, "title must be a non-empty string"),
        ({"title": 3}, "title must be a non-empty string"),
        ({"title": "x", "description": 3}, "description must be a string or null"),
        ({"title": "x", "status": "paused"}, "status must be one of: pending, in_progress, completed"),
        ({"title": "x", "due_date": "2026-2-1"}, "due_date must be an ISO-8601 date (YYYY-MM-DD) or null"),
        ({"title": "x", "priority": 1}, "Unknown field(s): priority"),
    ]
    for payload, message in cases:
        response = client.post("/tasks", json=payload)
        assert response.status_code == 400
        assert response.get_json() == {"error": message}


def test_create_requires_json_object(client):
    response = client.post("/tasks", data="[]", content_type="application/json")
    assert response.status_code == 400
    assert response.get_json() == {"error": "Request body must be a JSON object"}


def test_get_list_and_filter_tasks(client):
    first = create_task(client, title="First")
    create_task(client, title="Second", status="completed")
    response = client.get("/tasks")
    assert response.status_code == 200
    assert [task["id"] for task in response.get_json()] == [first["id"], 2]
    response = client.get("/tasks?status=completed")
    assert response.status_code == 200
    assert [task["title"] for task in response.get_json()] == ["Second"]


def test_list_rejects_invalid_status_filter(client):
    response = client.get("/tasks?status=unknown")
    assert response.status_code == 400
    assert response.get_json() == {"error": "status must be one of: pending, in_progress, completed"}


def test_get_task_and_missing_task(client):
    task = create_task(client)
    response = client.get(f"/tasks/{task['id']}")
    assert response.status_code == 200
    assert response.get_json() == task
    response = client.get("/tasks/999")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Task not found"}


def test_patch_task_updates_only_supplied_fields(client):
    task = create_task(client, description="Old", due_date="2026-01-01")
    response = client.patch(f"/tasks/{task['id']}", json={"title": "New", "status": "completed", "due_date": None})
    updated = response.get_json()
    assert response.status_code == 200
    assert updated["title"] == "New"
    assert updated["description"] == "Old"
    assert updated["status"] == "completed"
    assert updated["due_date"] is None
    assert updated["updated_at"] >= task["updated_at"]


def test_patch_rejects_empty_invalid_and_missing_tasks(client):
    task = create_task(client)
    cases = [({}, "Request body must include at least one updatable field"), ({"status": "bad"}, "status must be one of: pending, in_progress, completed")]
    for payload, message in cases:
        response = client.patch(f"/tasks/{task['id']}", json=payload)
        assert response.status_code == 400
        assert response.get_json() == {"error": message}
    response = client.patch("/tasks/999", json={"title": "No task"})
    assert response.status_code == 404
    assert response.get_json() == {"error": "Task not found"}


def test_delete_task(client):
    task = create_task(client)
    response = client.delete(f"/tasks/{task['id']}")
    assert response.status_code == 204
    assert response.data == b""
    assert client.get(f"/tasks/{task['id']}").status_code == 404
    response = client.delete(f"/tasks/{task['id']}")
    assert response.status_code == 404


def test_unknown_route_returns_json_404(client):
    response = client.get("/missing")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Not found"}


def test_migrations_are_idempotent(app):
    with app.app_context():
        assert migrate() == 0
