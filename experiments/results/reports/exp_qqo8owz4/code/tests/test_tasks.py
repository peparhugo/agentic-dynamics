from .conftest import register


def test_category_and_full_task_crud(client, auth_headers):
    category = client.post("/api/categories", headers=auth_headers, json={"name": "Work"})
    assert category.status_code == 201
    category_id = category.get_json()["category"]["id"]
    task = client.post("/api/tasks", headers=auth_headers, json={"title": "Ship API", "description": "Write tests", "status": "todo", "priority": "high", "due_date": "2026-12-01", "category_id": category_id})
    assert task.status_code == 201
    task_id = task.get_json()["task"]["id"]

    assert client.get(f"/api/tasks/{task_id}", headers=auth_headers).get_json()["task"]["title"] == "Ship API"
    updated = client.patch(f"/api/tasks/{task_id}", headers=auth_headers, json={"status": "completed", "due_date": None})
    assert updated.status_code == 200
    assert updated.get_json()["task"]["status"] == "completed"
    assert client.delete(f"/api/tasks/{task_id}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/tasks/{task_id}", headers=auth_headers).status_code == 404


def test_task_validation_and_category_ownership(client, auth_headers):
    assert client.post("/api/tasks", headers=auth_headers, json={"title": ""}).status_code == 400
    assert client.post("/api/tasks", headers=auth_headers, json={"title": "X", "priority": "now"}).status_code == 400
    assert client.post("/api/tasks", headers=auth_headers, json={"title": "X", "due_date": "tomorrow"}).status_code == 400
    other = register(client, "other@example.com")
    other_headers = {"Authorization": f"Bearer {other['token']}"}
    category_id = client.post("/api/categories", headers=other_headers, json={"name": "Private"}).get_json()["category"]["id"]
    assert client.post("/api/tasks", headers=auth_headers, json={"title": "X", "category_id": category_id}).status_code == 400


def test_assignment_visibility_and_owner_permissions(client, auth_headers):
    assignee = register(client, "assignee@example.com")
    task = client.post("/api/tasks", headers=auth_headers, json={"title": "Delegate", "assigned_to": assignee["user"]["id"]}).get_json()["task"]
    assignee_headers = {"Authorization": f"Bearer {assignee['token']}"}
    assert client.get(f"/api/tasks/{task['id']}", headers=assignee_headers).status_code == 200
    assert client.patch(f"/api/tasks/{task['id']}", headers=assignee_headers, json={"status": "completed"}).status_code == 403
    assert client.delete(f"/api/tasks/{task['id']}", headers=assignee_headers).status_code == 403


def test_task_listing_filters_search_and_pagination(client, auth_headers):
    work = client.post("/api/categories", headers=auth_headers, json={"name": "Work"}).get_json()["category"]
    for title, status, priority in [("Alpha report", "todo", "high"), ("Beta call", "completed", "low"), ("Alpha review", "todo", "high")]:
        assert client.post("/api/tasks", headers=auth_headers, json={"title": title, "status": status, "priority": priority, "category_id": work["id"]}).status_code == 201
    response = client.get("/api/tasks?status=todo&priority=high&search=Alpha&per_page=1&page=2", headers=auth_headers)
    body = response.get_json()
    assert response.status_code == 200
    assert body["pagination"] == {"page": 2, "per_page": 1, "total": 2, "pages": 2}
    assert len(body["tasks"]) == 1
    assert client.get("/api/tasks?status=nope", headers=auth_headers).status_code == 400
