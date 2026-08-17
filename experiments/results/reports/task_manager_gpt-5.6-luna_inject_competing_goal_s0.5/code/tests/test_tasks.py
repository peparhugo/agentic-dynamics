from .conftest import register, token


def create(client, auth, **values):
    body = {"title": "Plan release", **values}
    return client.post("/api/tasks", json=body, headers=auth)


def test_task_crud_and_fields(client, auth):
    response = create(client, auth, description="Ship it", category="work", priority="high", due_date="2026-09-01")
    assert response.status_code == 201
    task = response.get_json()["task"]
    assert task["status"] == "todo" and task["priority"] == "high"
    task_id = task["id"]
    assert client.get(f"/api/tasks/{task_id}", headers=auth).status_code == 200
    updated = client.patch(f"/api/tasks/{task_id}", json={"status": "done"}, headers=auth)
    assert updated.get_json()["task"]["status"] == "done"
    assert client.delete(f"/api/tasks/{task_id}", headers=auth).status_code == 204
    assert client.get(f"/api/tasks/{task_id}", headers=auth).status_code == 404


def test_filters_search_and_pagination(client, auth):
    create(client, auth, title="Write report", category="work", priority="high", status="in_progress")
    create(client, auth, title="Buy groceries", category="home", priority="low")
    response = client.get("/api/tasks?category=work&search=report&per_page=1", headers=auth)
    data = response.get_json()
    assert data["pagination"] == {"page": 1, "per_page": 1, "total": 1, "pages": 1}
    assert data["items"][0]["title"] == "Write report"


def test_invalid_task_data_is_rejected(client, auth):
    assert create(client, auth, title="", priority="critical").status_code == 400
    assert create(client, auth, due_date="tomorrow").status_code == 400


def test_assignment_and_access_control(client, auth):
    second = token(client, "bob", "bob@example.com")
    bob = {"Authorization": f"Bearer {second}"}
    first = create(client, auth, assignee_id=2).get_json()["task"]
    assert client.get(f"/api/tasks/{first['id']}", headers=bob).status_code == 200
    assert client.post("/api/tasks", json={"title": "Nope", "assignee_id": 999}, headers=auth).status_code == 400


def test_unknown_task_is_not_found(client, auth):
    assert client.get("/api/tasks/999", headers=auth).status_code == 404
    assert client.delete("/api/tasks/999", headers=auth).status_code == 404
