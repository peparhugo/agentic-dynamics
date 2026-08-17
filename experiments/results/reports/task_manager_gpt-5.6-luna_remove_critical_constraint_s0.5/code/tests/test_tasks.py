from datetime import datetime

from conftest import create


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_create_applies_defaults_and_returns_timestamps(client):
    task = create(client, "Buy milk")
    assert task["title"] == "Buy milk"
    assert task["description"] == ""
    assert task["status"] == "pending"
    assert task["priority"] == "medium"
    assert task["due_date"] is None
    datetime.fromisoformat(task["created_at"])
    assert task["created_at"] == task["updated_at"]


def test_create_and_get_preserve_all_fields(client):
    task = create(client, "Ship release", description="Publish notes", status="completed", priority="high", due_date="2026-09-01")
    response = client.get(f"/api/v1/tasks/{task['id']}")
    assert response.status_code == 200
    assert response.json["description"] == "Publish notes"
    assert response.json["due_date"] == "2026-09-01"


def test_list_filters_searches_and_paginates(client):
    create(client, "Write API", description="backend work", priority="high")
    create(client, "Buy groceries", due_date="2026-09-10")
    create(client, "Review API", status="completed", due_date="2026-09-02")
    response = client.get("/api/v1/tasks?status=completed&due_before=2026-09-05&q=api&page=1&per_page=1")
    assert response.status_code == 200
    assert response.json["total"] == 1
    assert len(response.json["data"]) == 1
    assert response.json["data"][0]["title"] == "Review API"


def test_list_sorting_and_second_page(client):
    create(client, "Zeta")
    create(client, "Alpha")
    response = client.get("/api/v1/tasks?sort=title&order=asc&per_page=1&page=2")
    assert response.json["data"][0]["title"] == "Zeta"


def test_update_is_partial_and_changes_updated_at(client):
    task = create(client, "Old", description="details")
    response = client.patch(f"/api/v1/tasks/{task['id']}", json={"title": "New", "due_date": None})
    assert response.status_code == 200
    assert response.json["title"] == "New"
    assert response.json["description"] == "details"
    assert response.json["updated_at"] >= task["updated_at"]


def test_delete_removes_task(client):
    task = create(client, "Temporary")
    assert client.delete(f"/api/v1/tasks/{task['id']}").status_code == 204
    assert client.get(f"/api/v1/tasks/{task['id']}").status_code == 404
    assert client.delete(f"/api/v1/tasks/{task['id']}").status_code == 404


def test_validation_errors(client):
    cases = [
        ({}, "title is required"),
        ({"title": " "}, "non-empty"),
        ({"title": "x", "status": "later"}, "status"),
        ({"title": "x", "priority": "urgent"}, "priority"),
        ({"title": "x", "due_date": "tomorrow"}, "ISO date"),
        ({"title": "x", "unexpected": True}, "unknown fields"),
    ]
    for payload, expected in cases:
        response = client.post("/api/v1/tasks", json=payload)
        assert response.status_code == 400
        assert expected in response.json["error"]


def test_missing_and_invalid_list_parameters(client):
    assert client.get("/api/v1/tasks/999").status_code == 404
    for query in ("?page=no", "?per_page=0", "?sort=wat", "?status=other", "?order=random"):
        response = client.get("/api/v1/tasks" + query)
        assert response.status_code == 400


def test_patch_requires_fields_and_valid_json_object(client):
    task = create(client, "Task")
    assert client.patch(f"/api/v1/tasks/{task['id']}", json={}).status_code == 400
    assert client.patch(f"/api/v1/tasks/{task['id']}", json=[]).status_code == 400
