from conftest import register


def create_category(client, auth, name="Work"):
    return client.post("/categories", headers=auth, json={"name": name})


def create_task(client, auth, **values):
    data = {"title": "Plan release", "description": "Prepare notes", "status": "todo", "priority": "high"}
    data.update(values)
    return client.post("/tasks", headers=auth, json=data)


def test_register_login_and_duplicate_username(client):
    assert register(client).status_code == 201
    assert register(client).status_code == 409
    assert client.post("/auth/login", json={"username": "alice", "password": "password123"}).status_code == 200
    assert client.post("/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401


def test_registration_validates_input(client):
    assert register(client, "", "short").status_code == 400
    assert client.post("/auth/login", json={}).status_code == 401


def test_protected_routes_require_token(client):
    assert client.get("/tasks").status_code == 401
    assert client.get("/categories", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_category_lifecycle_and_ownership(client, auth):
    category = create_category(client, auth).get_json()
    assert client.get("/categories", headers=auth).get_json()["categories"][0]["name"] == "Work"
    assert create_category(client, auth).status_code == 409
    assert client.delete(f"/categories/{category['id']}", headers=auth).status_code == 204
    assert client.delete(f"/categories/{category['id']}", headers=auth).status_code == 404


def test_create_read_update_delete_task(client, auth):
    category = create_category(client, auth).get_json()
    task = create_task(client, auth, category_id=category["id"], due_date="2026-12-01").get_json()
    assert task["category_name"] == "Work"
    assert client.get(f"/tasks/{task['id']}", headers=auth).status_code == 200
    updated = client.patch(f"/tasks/{task['id']}", headers=auth, json={"status": "completed", "priority": "low", "due_date": None})
    assert updated.status_code == 200
    assert updated.get_json()["status"] == "completed"
    assert updated.get_json()["due_date"] is None
    assert client.delete(f"/tasks/{task['id']}", headers=auth).status_code == 204
    assert client.get(f"/tasks/{task['id']}", headers=auth).status_code == 404


def test_task_validation(client, auth):
    assert client.post("/tasks", headers=auth, json={}).status_code == 400
    assert create_task(client, auth, status="later").status_code == 400
    assert create_task(client, auth, priority="urgent").status_code == 400
    assert create_task(client, auth, due_date="12/01/2026").status_code == 400
    assert create_task(client, auth, category_id=999).status_code == 400
    task = create_task(client, auth).get_json()
    assert client.patch(f"/tasks/{task['id']}", headers=auth, json={}).status_code == 400


def test_task_filters_search_and_pagination(client, auth):
    work = create_category(client, auth, "Work").get_json()
    home = create_category(client, auth, "Home").get_json()
    create_task(client, auth, title="Write report", status="todo", priority="high", category_id=work["id"])
    create_task(client, auth, title="Buy milk", status="completed", priority="low", category_id=home["id"])
    create_task(client, auth, title="Review report", status="todo", priority="medium", category_id=work["id"])
    response = client.get(f"/tasks?status=todo&category_id={work['id']}&q=report&per_page=1", headers=auth)
    body = response.get_json()
    assert response.status_code == 200
    assert body["pagination"] == {"page": 1, "per_page": 1, "total": 2, "pages": 2}
    assert len(body["tasks"]) == 1
    assert client.get("/tasks?priority=bad", headers=auth).status_code == 400
    assert client.get("/tasks?page=0", headers=auth).status_code == 400


def test_assignment_and_task_authorization(client, auth):
    register(client, "bob")
    login = client.post("/auth/login", json={"username": "bob", "password": "password123"}).get_json()
    bob_auth = {"Authorization": f"Bearer {login['access_token']}"}
    task = create_task(client, auth, assignee_id=2).get_json()
    assert client.get(f"/tasks/{task['id']}", headers=bob_auth).status_code == 200
    assert client.patch(f"/tasks/{task['id']}", headers=bob_auth, json={"title": "Nope"}).status_code == 404
    assert client.delete(f"/tasks/{task['id']}", headers=bob_auth).status_code == 404
    assert create_task(client, auth, assignee_id=999).status_code == 400


def test_category_deletion_clears_task_category(client, auth):
    category = create_category(client, auth).get_json()
    task = create_task(client, auth, category_id=category["id"]).get_json()
    client.delete(f"/categories/{category['id']}", headers=auth)
    assert client.get(f"/tasks/{task['id']}", headers=auth).get_json()["category_id"] is None
