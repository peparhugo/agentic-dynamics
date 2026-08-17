from conftest import register


def create(client, auth, **overrides):
    payload = {"title": "Write docs", "description": "API documentation", "category": "work", "priority": "high", "due_date": "2026-09-01"}
    payload.update(overrides)
    return client.post("/api/tasks", headers=auth, json=payload)


def test_create_and_read_task_with_defaults(client, auth):
    response = create(client, auth)

    assert response.status_code == 201
    task = response.get_json()["task"]
    assert task["status"] == "todo"
    assert task["priority"] == "high"
    assert task["owner_id"] == 1
    response = client.get(f"/api/tasks/{task['id']}", headers=auth)
    assert response.status_code == 200
    assert response.get_json()["task"]["title"] == "Write docs"


def test_create_validates_task_fields(client, auth):
    assert client.post("/api/tasks", headers=auth, json={}).status_code == 400
    assert create(client, auth, priority="critical").status_code == 400
    assert create(client, auth, due_date="next Tuesday").status_code == 400
    assert create(client, auth, unexpected=True).status_code == 400
    assert create(client, auth, assignee_id=999).status_code == 400


def test_owner_can_update_and_delete_task(client, auth):
    task_id = create(client, auth).get_json()["task"]["id"]
    response = client.patch(f"/api/tasks/{task_id}", headers=auth, json={"title": "Revised", "status": "completed", "due_date": None})

    assert response.status_code == 200
    assert response.get_json()["task"]["status"] == "completed"
    assert response.get_json()["task"]["due_date"] is None
    assert client.delete(f"/api/tasks/{task_id}", headers=auth).status_code == 204
    assert client.get(f"/api/tasks/{task_id}", headers=auth).status_code == 404


def test_only_owner_can_modify_but_assignee_can_view(client, auth):
    assignee = register(client, "assignee@example.com", name="Assignee").get_json()
    assignee_auth = {"Authorization": f"Bearer {assignee['token']}"}
    task_id = create(client, auth, assignee_id=assignee["user"]["id"]).get_json()["task"]["id"]

    assert client.get(f"/api/tasks/{task_id}", headers=assignee_auth).status_code == 200
    assert client.patch(f"/api/tasks/{task_id}", headers=assignee_auth, json={"title": "Nope"}).status_code == 404
    assert client.delete(f"/api/tasks/{task_id}", headers=assignee_auth).status_code == 404


def test_list_filters_search_and_pagination(client, auth):
    create(client, auth, title="Buy milk", description="Groceries", category="home", priority="low")
    create(client, auth, title="Deploy API", category="work", status="in_progress", priority="urgent")
    create(client, auth, title="Review API", category="work", status="completed")

    filtered = client.get("/api/tasks?status=in_progress&category=work&priority=urgent", headers=auth).get_json()
    assert filtered["total"] == 1
    assert filtered["tasks"][0]["title"] == "Deploy API"
    searched = client.get("/api/tasks?search=API&page=1&per_page=1", headers=auth).get_json()
    assert searched["total"] == 2
    assert len(searched["tasks"]) == 1
    assert client.get("/api/tasks?status=bad", headers=auth).status_code == 400
    assert client.get("/api/tasks?page=0", headers=auth).status_code == 400


def test_tasks_are_not_visible_to_unrelated_users(client, auth):
    task_id = create(client, auth).get_json()["task"]["id"]
    other = register(client, "other@example.com", name="Other").get_json()
    other_auth = {"Authorization": f"Bearer {other['token']}"}

    assert client.get("/api/tasks", headers=other_auth).get_json()["tasks"] == []
    assert client.get(f"/api/tasks/{task_id}", headers=other_auth).status_code == 404
