import pytest


def test_create_task_with_all_fields(client, users, create_task):
    response = create_task(
        title="Ship API",
        description="Finish implementation",
        status="in_progress",
        category="Work",
        priority="high",
        due_date="2027-01-15",
        assignee_id=users["bob"]["id"],
    )
    assert response.status_code == 201
    task = response.get_json()
    assert task["title"] == "Ship API"
    assert task["creator_username"] == "alice"
    assert task["assignee_username"] == "bob"
    assert task["priority"] == "high"


def test_create_applies_defaults(create_task):
    response = create_task()
    task = response.get_json()
    assert response.status_code == 201
    assert task["description"] == ""
    assert task["status"] == "pending"
    assert task["priority"] == "medium"
    assert task["due_date"] is None


@pytest.mark.parametrize(
    "payload,error_text",
    [
        ({"category": "Work"}, "title is required"),
        ({"title": "Task"}, "category is required"),
        ({"title": "Task", "category": "Work", "status": "open"}, "invalid status"),
        ({"title": "Task", "category": "Work", "priority": "urgent"}, "invalid priority"),
        ({"title": "Task", "category": "Work", "due_date": "tomorrow"}, "due_date"),
        ({"title": "Task", "category": "Work", "extra": True}, "unknown field"),
        ({"title": "Task", "category": "Work", "assignee_id": 9999}, "assignee"),
    ],
)
def test_create_validation(client, users, payload, error_text):
    response = client.post("/tasks", json=payload, headers=users["alice"]["headers"])
    assert response.status_code == 400
    assert error_text in response.get_json()["error"]


def test_get_task_visibility(client, users, create_task):
    task = create_task(assignee_id=users["bob"]["id"]).get_json()
    assert client.get(
        f"/tasks/{task['id']}", headers=users["alice"]["headers"]
    ).status_code == 200
    assert client.get(
        f"/tasks/{task['id']}", headers=users["bob"]["headers"]
    ).status_code == 200
    assert client.get(
        f"/tasks/{task['id']}", headers=users["charlie"]["headers"]
    ).status_code == 404


def test_creator_can_update_and_reassign(client, users, create_task):
    task = create_task().get_json()
    response = client.patch(
        f"/tasks/{task['id']}",
        json={
            "title": "Updated",
            "status": "completed",
            "assignee_id": users["bob"]["id"],
        },
        headers=users["alice"]["headers"],
    )
    assert response.status_code == 200
    assert response.get_json()["title"] == "Updated"
    assert response.get_json()["status"] == "completed"
    assert response.get_json()["assignee_username"] == "bob"


def test_assignee_can_update_but_not_reassign(client, users, create_task):
    task = create_task(assignee_id=users["bob"]["id"]).get_json()
    response = client.patch(
        f"/tasks/{task['id']}",
        json={"status": "in_progress"},
        headers=users["bob"]["headers"],
    )
    assert response.status_code == 200
    response = client.patch(
        f"/tasks/{task['id']}",
        json={"assignee_id": users["charlie"]["id"]},
        headers=users["bob"]["headers"],
    )
    assert response.status_code == 403


def test_update_validation(client, users, create_task):
    task = create_task().get_json()
    assert client.patch(
        f"/tasks/{task['id']}", json={}, headers=users["alice"]["headers"]
    ).status_code == 400
    assert client.patch(
        f"/tasks/{task['id']}",
        json={"due_date": "01/02/2027"},
        headers=users["alice"]["headers"],
    ).status_code == 400


def test_only_creator_can_delete(client, users, create_task):
    task = create_task(assignee_id=users["bob"]["id"]).get_json()
    response = client.delete(
        f"/tasks/{task['id']}", headers=users["bob"]["headers"]
    )
    assert response.status_code == 403
    response = client.delete(
        f"/tasks/{task['id']}", headers=users["alice"]["headers"]
    )
    assert response.status_code == 204
    assert client.get(
        f"/tasks/{task['id']}", headers=users["alice"]["headers"]
    ).status_code == 404


def test_list_only_includes_visible_tasks(client, users, create_task):
    create_task(title="Owned")
    create_task(owner="bob", title="Assigned", assignee_id=users["alice"]["id"])
    create_task(owner="charlie", title="Hidden")
    response = client.get("/tasks", headers=users["alice"]["headers"])
    assert response.status_code == 200
    assert {item["title"] for item in response.get_json()["items"]} == {"Owned", "Assigned"}
    assert response.get_json()["total"] == 2


def test_filters_and_search_can_be_combined(client, users, create_task):
    create_task(title="Release docs", description="public guide", category="Docs", priority="high")
    create_task(title="Release code", description="internal", category="Engineering", priority="high")
    create_task(title="Old docs", category="Docs", priority="low", status="completed")
    response = client.get(
        "/tasks?search=release&category=docs&priority=high&status=pending",
        headers=users["alice"]["headers"],
    )
    assert response.status_code == 200
    assert [item["title"] for item in response.get_json()["items"]] == ["Release docs"]


def test_invalid_filter_is_rejected(client, users):
    assert client.get(
        "/tasks?status=unknown", headers=users["alice"]["headers"]
    ).status_code == 400
    assert client.get(
        "/tasks?priority=urgent", headers=users["alice"]["headers"]
    ).status_code == 400


def test_pagination(client, users, create_task):
    for number in range(5):
        create_task(title=f"Task {number}")
    first = client.get("/tasks?page=1&per_page=2", headers=users["alice"]["headers"])
    third = client.get("/tasks?page=3&per_page=2", headers=users["alice"]["headers"])
    assert first.get_json()["total"] == 5
    assert len(first.get_json()["items"]) == 2
    assert first.get_json()["items"][0]["title"] == "Task 4"
    assert len(third.get_json()["items"]) == 1


@pytest.mark.parametrize("query", ["page=0", "per_page=0", "per_page=101", "page=x"])
def test_invalid_pagination(client, users, query):
    response = client.get(f"/tasks?{query}", headers=users["alice"]["headers"])
    assert response.status_code == 400
