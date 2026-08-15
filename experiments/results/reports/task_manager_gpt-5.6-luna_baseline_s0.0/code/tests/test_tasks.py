from .conftest import register


def create_task(client, auth, **overrides):
    data = {"title": "Write tests", "description": "API coverage", "status": "todo", "category": "work", "priority": "high", "due_date": "2030-01-02", **overrides}
    return client.post("/api/tasks", json=data, headers=auth)


def test_create_and_read_task_with_assignment(client, auth):
    bob = register(client).get_json()["user"]["id"]
    response = create_task(client, auth, assigned_to=bob)
    assert response.status_code == 201
    task = response.get_json()
    assert task["assignee"]["id"] == bob
    assert client.get("/api/tasks/" + str(task["id"]), headers=auth).get_json()["title"] == "Write tests"


def test_update_patch_and_delete_task(client, auth):
    task = create_task(client, auth).get_json()
    response = client.patch(f"/api/tasks/{task['id']}", json={"status": "completed", "priority": "low"}, headers=auth)
    assert response.status_code == 200
    assert response.get_json()["status"] == "completed"
    assert client.put(f"/api/tasks/{task['id']}", json={"title": "Updated"}, headers=auth).status_code == 200
    assert client.delete(f"/api/tasks/{task['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/tasks/{task['id']}", headers=auth).status_code == 404


def test_filters_search_and_pagination(client, auth):
    create_task(client, auth, title="Urgent bug", category="bugs", priority="urgent")
    create_task(client, auth, title="Plan meeting", category="admin", priority="low", status="completed")
    create_task(client, auth, title="Another bug", category="bugs", priority="high")
    response = client.get("/api/tasks?category=bugs&search=bug&page=1&per_page=1", headers=auth)
    body = response.get_json()
    assert response.status_code == 200
    assert len(body["tasks"]) == 1
    assert body["pagination"] == {"page": 1, "per_page": 1, "total": 2, "pages": 2}


def test_validation_and_missing_task(client, auth):
    assert create_task(client, auth, status="bad").status_code == 400
    assert create_task(client, auth, due_date="not-a-date").status_code == 400
    assert create_task(client, auth, assigned_to=999).status_code == 400
    assert client.get("/api/tasks/999", headers=auth).status_code == 404
    assert client.patch("/api/tasks/999", json={"title": "x"}, headers=auth).status_code == 404


def test_users_and_categories(client, auth):
    create_task(client, auth, category="personal")
    assert len(client.get("/api/users", headers=auth).get_json()["users"]) == 1
    categories = client.get("/api/categories", headers=auth).get_json()["categories"]
    assert categories == [{"name": "personal", "count": 1}]
