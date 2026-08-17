import pytest


def create_task(client, headers, **overrides):
    payload = {"title": "Write tests", "description": "Cover the API"}
    payload.update(overrides)
    return client.post("/api/tasks", json=payload, headers=headers)


def test_create_and_read_task(client, auth_headers, category, second_user):
    response = create_task(
        client,
        auth_headers,
        status="in_progress",
        priority="high",
        due_date="2026-08-20T14:30:00+02:00",
        category_id=category["id"],
        assignee_id=second_user["user"]["id"],
    )
    assert response.status_code == 201
    task = response.get_json()["task"]
    assert task["due_date"] == "2026-08-20T12:30:00Z"
    assert task["category_name"] == "Work"
    assert task["assignee_username"] == "bob"
    assert task["creator_username"] == "alice"
    assert client.get(f"/api/tasks/{task['id']}", headers=auth_headers).get_json()["task"] == task


def test_create_task_defaults(client, auth_headers):
    task = create_task(client, auth_headers, title="  A task  ").get_json()["task"]
    assert task["title"] == "A task"
    assert task["description"] == "Cover the API"
    assert task["status"] == "todo"
    assert task["priority"] == "medium"
    assert task["due_date"] is None


@pytest.mark.parametrize(
    "payload,field",
    [
        ({}, "title"),
        ({"title": ""}, "title"),
        ({"title": "Task", "status": "started"}, "status"),
        ({"title": "Task", "priority": "critical"}, "priority"),
        ({"title": "Task", "due_date": "tomorrow"}, "due_date"),
        ({"title": "Task", "category_id": 999}, "category_id"),
        ({"title": "Task", "assignee_id": "1"}, "assignee_id"),
    ],
)
def test_create_task_validation(client, auth_headers, payload, field):
    response = client.post("/api/tasks", json=payload, headers=auth_headers)
    assert response.status_code == 400
    assert field in response.get_json()["details"]


def test_update_task_and_clear_nullable_fields(client, auth_headers, category, second_user):
    task = create_task(
        client,
        auth_headers,
        category_id=category["id"],
        assignee_id=second_user["user"]["id"],
        due_date="2026-01-01T00:00:00Z",
    ).get_json()["task"]
    response = client.patch(
        f"/api/tasks/{task['id']}",
        json={
            "title": "Finished task",
            "description": "Done",
            "status": "completed",
            "priority": "urgent",
            "category_id": None,
            "assignee_id": None,
            "due_date": None,
        },
        headers=auth_headers,
    )
    updated = response.get_json()["task"]
    assert response.status_code == 200
    assert updated["title"] == "Finished task"
    assert updated["status"] == "completed"
    assert updated["priority"] == "urgent"
    assert updated["category_id"] is None
    assert updated["assignee_id"] is None
    assert updated["due_date"] is None


def test_update_rejects_empty_or_invalid_changes(client, auth_headers):
    task_id = create_task(client, auth_headers).get_json()["task"]["id"]
    assert client.patch(f"/api/tasks/{task_id}", json={"unknown": 1}, headers=auth_headers).status_code == 400
    response = client.patch(f"/api/tasks/{task_id}", json={"status": "bad"}, headers=auth_headers)
    assert response.status_code == 400
    assert response.get_json()["details"]["status"]


def test_delete_task_and_not_found_responses(client, auth_headers):
    task_id = create_task(client, auth_headers).get_json()["task"]["id"]
    assert client.delete(f"/api/tasks/{task_id}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/tasks/{task_id}", headers=auth_headers).status_code == 404
    assert client.patch(f"/api/tasks/{task_id}", json={"title": "x"}, headers=auth_headers).status_code == 404
    assert client.delete(f"/api/tasks/{task_id}", headers=auth_headers).status_code == 404


def test_search_and_filters(client, auth_headers, category, second_user):
    bob_id = second_user["user"]["id"]
    create_task(
        client, auth_headers, title="Deploy website", description="production release",
        status="in_progress", priority="urgent", category_id=category["id"], assignee_id=bob_id,
    )
    create_task(client, auth_headers, title="Buy milk", status="todo", priority="low")
    checks = {
        "status=in_progress": "Deploy website",
        "priority=low": "Buy milk",
        f"category={category['id']}": "Deploy website",
        "category=work": "Deploy website",
        f"assignee_id={bob_id}": "Deploy website",
        "q=release": "Deploy website",
        "q=MILK": "Buy milk",
        "status=in_progress&priority=urgent&q=deploy": "Deploy website",
    }
    for query, expected in checks.items():
        response = client.get(f"/api/tasks?{query}", headers=auth_headers)
        assert response.status_code == 200
        assert [task["title"] for task in response.get_json()["tasks"]] == [expected]


def test_pagination(client, auth_headers):
    for number in range(5):
        create_task(client, auth_headers, title=f"Task {number}")
    first = client.get("/api/tasks?page=1&per_page=2", headers=auth_headers).get_json()
    third = client.get("/api/tasks?page=3&per_page=2", headers=auth_headers).get_json()
    assert first["pagination"] == {"page": 1, "per_page": 2, "total": 5, "pages": 3}
    assert len(first["tasks"]) == 2
    assert len(third["tasks"]) == 1


@pytest.mark.parametrize(
    "query",
    ["page=zero", "page=0", "per_page=0", "per_page=101", "status=bad", "priority=bad", "assignee_id=x"],
)
def test_invalid_list_parameters(client, auth_headers, query):
    assert client.get(f"/api/tasks?{query}", headers=auth_headers).status_code == 400


def test_category_task_count(client, auth_headers, category):
    create_task(client, auth_headers, category_id=category["id"])
    create_task(client, auth_headers, category_id=category["id"], title="Another")
    categories = client.get("/api/categories", headers=auth_headers).get_json()["categories"]
    assert categories[0]["task_count"] == 2
