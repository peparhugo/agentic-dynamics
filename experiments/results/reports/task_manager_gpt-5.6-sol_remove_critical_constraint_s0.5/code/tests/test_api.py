import re


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_create_task_with_defaults(client):
    response = client.post("/tasks", json={"title": "  Buy milk  "})
    body = response.get_json()

    assert response.status_code == 201
    assert response.headers["Location"] == f"/tasks/{body['id']}"
    assert body["title"] == "Buy milk"
    assert body["description"] is None
    assert body["status"] == "todo"
    assert body["priority"] == "medium"
    assert body["due_date"] is None
    assert body["completed_at"] is None
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T.*Z", body["created_at"])
    assert body["updated_at"] == body["created_at"]


def test_create_task_with_all_fields(client):
    response = client.post(
        "/tasks",
        json={
            "title": "Ship release",
            "description": "Tag and publish",
            "status": "completed",
            "priority": "high",
            "due_date": "2026-08-20",
        },
    )
    body = response.get_json()

    assert response.status_code == 201
    assert body["description"] == "Tag and publish"
    assert body["status"] == "completed"
    assert body["priority"] == "high"
    assert body["due_date"] == "2026-08-20"
    assert body["completed_at"] is not None


def test_get_task_and_missing_task(client, create_task):
    task = create_task()
    assert client.get(f"/tasks/{task['id']}").get_json() == task

    response = client.get("/tasks/999")
    assert response.status_code == 404
    assert response.get_json()["error"]["message"] == "Task not found"


def test_create_requires_json_object_and_title(client):
    response = client.post("/tasks", data="title=x", content_type="text/plain")
    assert response.status_code == 415

    response = client.post("/tasks", json=[])
    assert response.status_code == 400
    assert "body" in response.get_json()["error"]["fields"]

    response = client.post("/tasks", json={})
    assert response.status_code == 400
    assert response.get_json()["error"]["fields"]["title"] == "is required"


def test_create_rejects_invalid_fields(client):
    cases = [
        ({"title": "  "}, "title"),
        ({"title": 12}, "title"),
        ({"title": "x" * 201}, "title"),
        ({"title": "x", "description": 4}, "description"),
        ({"title": "x", "status": "blocked"}, "status"),
        ({"title": "x", "priority": "urgent"}, "priority"),
        ({"title": "x", "due_date": "tomorrow"}, "due_date"),
        ({"title": "x", "owner": "me"}, "unknown"),
    ]
    for payload, field in cases:
        response = client.post("/tasks", json=payload)
        assert response.status_code == 400
        assert field in response.get_json()["error"]["fields"]


def test_patch_updates_only_supplied_fields(client, create_task):
    task = create_task(description="original", priority="low", due_date="2026-09-01")
    response = client.patch(f"/tasks/{task['id']}", json={"title": "Changed"})
    body = response.get_json()

    assert response.status_code == 200
    assert body["title"] == "Changed"
    assert body["description"] == "original"
    assert body["priority"] == "low"
    assert body["due_date"] == "2026-09-01"


def test_patch_rejects_empty_body(client, create_task):
    task = create_task()
    response = client.patch(f"/tasks/{task['id']}", json={})
    assert response.status_code == 400
    assert "body" in response.get_json()["error"]["fields"]


def test_put_replaces_optional_fields(client, create_task):
    task = create_task(description="old", status="in_progress", priority="high", due_date="2026-09-01")
    response = client.put(f"/tasks/{task['id']}", json={"title": "Replacement"})
    body = response.get_json()

    assert response.status_code == 200
    assert body["title"] == "Replacement"
    assert body["description"] is None
    assert body["status"] == "todo"
    assert body["priority"] == "medium"
    assert body["due_date"] is None


def test_completion_and_reopening_manage_completed_at(client, create_task):
    task = create_task()
    completed = client.post(f"/tasks/{task['id']}/complete").get_json()
    assert completed["status"] == "completed"
    assert completed["completed_at"] is not None

    repeated = client.post(f"/tasks/{task['id']}/complete").get_json()
    assert repeated["completed_at"] == completed["completed_at"]

    reopened = client.patch(f"/tasks/{task['id']}", json={"status": "in_progress"}).get_json()
    assert reopened["status"] == "in_progress"
    assert reopened["completed_at"] is None


def test_update_missing_task_returns_404_before_body_validation(client):
    assert client.patch("/tasks/99", json={"title": "x"}).status_code == 404
    assert client.put("/tasks/99", json={"title": "x"}).status_code == 404
    assert client.post("/tasks/99/complete").status_code == 404


def test_delete_task(client, create_task):
    task = create_task()
    response = client.delete(f"/tasks/{task['id']}")
    assert response.status_code == 204
    assert response.data == b""
    assert client.get(f"/tasks/{task['id']}").status_code == 404
    assert client.delete(f"/tasks/{task['id']}").status_code == 404


def test_list_is_paginated(client, create_task):
    for index in range(5):
        create_task(title=f"Task {index}")

    response = client.get("/tasks?page=2&per_page=2&sort=title&direction=asc")
    body = response.get_json()
    assert [item["title"] for item in body["items"]] == ["Task 2", "Task 3"]
    assert body["pagination"] == {"page": 2, "per_page": 2, "total": 5, "pages": 3}


def test_list_filters_and_searches(client, create_task):
    create_task(title="Alpha report", description="finance", status="todo", priority="high", due_date="2026-08-10")
    create_task(title="Beta", description="alpha mention", status="completed", priority="low", due_date="2026-08-25")
    create_task(title="Gamma", description="other", status="todo", priority="high", due_date="2026-09-01")

    assert len(client.get("/tasks?status=todo&priority=high").get_json()["items"]) == 2
    assert len(client.get("/tasks?q=ALPHA").get_json()["items"]) == 2
    due = client.get("/tasks?due_before=2026-08-20").get_json()["items"]
    assert [item["title"] for item in due] == ["Alpha report"]


def test_list_validates_query_parameters(client):
    invalid_queries = [
        "page=0", "page=no", "per_page=0", "per_page=no", "per_page=101",
        "status=blocked", "priority=urgent", "sort=id", "direction=sideways",
        "due_before=soon",
    ]
    for query in invalid_queries:
        response = client.get(f"/tasks?{query}")
        assert response.status_code == 400, query
        assert response.get_json()["error"]["fields"], query


def test_unknown_route_has_json_error(client):
    response = client.get("/unknown")
    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["error"]["code"] == "Not Found"
