from .conftest import register, token


def task_payload(**overrides):
    value = {"title": "Ship API", "description": "Finish the endpoint", "category": "work", "priority": "high", "status": "in_progress", "due_date": "2030-01-15"}
    value.update(overrides)
    return value


def test_create_read_update_delete_task(client, auth):
    created = client.post("/api/tasks", json=task_payload(), headers=auth)
    assert created.status_code == 201
    task = created.get_json()["task"]
    assert task["title"] == "Ship API" and task["assignee"] is None
    task_id = task["id"]
    assert client.get(f"/api/tasks/{task_id}", headers=auth).get_json()["task"]["status"] == "in_progress"
    updated = client.patch(f"/api/tasks/{task_id}", json={"status": "completed", "priority": "urgent"}, headers=auth)
    assert updated.status_code == 200
    assert updated.get_json()["task"]["status"] == "completed"
    assert client.delete(f"/api/tasks/{task_id}", headers=auth).status_code == 204
    assert client.get(f"/api/tasks/{task_id}", headers=auth).status_code == 404


def test_task_validation(client, auth):
    assert client.post("/api/tasks", json={}, headers=auth).status_code == 400
    assert client.post("/api/tasks", json=task_payload(status="bad"), headers=auth).status_code == 400
    assert client.post("/api/tasks", json=task_payload(due_date="tomorrow"), headers=auth).status_code == 400


def test_assignment_and_assignee_access(client, auth):
    bob = register(client, "bob").get_json()
    created = client.post("/api/tasks", json=task_payload(assignee_id=bob["user"]["id"]), headers=auth)
    assert created.status_code == 201
    assert created.get_json()["task"]["assignee"]["username"] == "bob"
    bob_headers = {"Authorization": f"Bearer {bob['token']}"}
    assert client.get("/api/tasks", headers=bob_headers).get_json()["pagination"]["total"] == 1
    assert client.patch(f"/api/tasks/{created.get_json()['task']['id']}", json={"status": "completed"}, headers=bob_headers).status_code == 200
    assert client.delete(f"/api/tasks/{created.get_json()['task']['id']}", headers=bob_headers).status_code == 403


def test_task_access_is_scoped_to_owner_or_assignee(client, auth):
    outsider = {"Authorization": f"Bearer {token(client, 'charlie')}"}
    created = client.post("/api/tasks", json=task_payload(), headers=auth).get_json()["task"]
    assert client.get(f"/api/tasks/{created['id']}", headers=outsider).status_code == 403
    assert client.get("/api/tasks", headers=outsider).get_json()["pagination"]["total"] == 0


def test_search_filters_and_pagination(client, auth):
    for index in range(5):
        response = client.post("/api/tasks", json=task_payload(title=f"Project {index}", status="completed" if index % 2 else "todo", category="personal" if index == 4 else "work"), headers=auth)
        assert response.status_code == 201
    response = client.get("/api/tasks?status=completed&category=work&search=project&page=1&per_page=1", headers=auth)
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["pagination"] == {"page": 1, "per_page": 1, "total": 2, "pages": 2}
    assert len(payload["tasks"]) == 1


def test_missing_task_and_bad_pagination(client, auth):
    assert client.get("/api/tasks/999", headers=auth).status_code == 404
    assert client.get("/api/tasks?page=x", headers=auth).status_code == 400
