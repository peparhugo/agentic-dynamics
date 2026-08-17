from .conftest import auth, register


def test_register_login_and_duplicate_email(client):
    response = register(client)
    assert response.status_code == 201
    assert response.json["user"]["email"] == "alice@example.com"
    assert response.json["token"]
    assert register(client, "ALICE@example.com").status_code == 409
    login = client.post("/api/auth/login", json={"email": "ALICE@example.com", "password": "password123"})
    assert login.status_code == 200
    assert client.post("/api/auth/login", json={"email": "alice@example.com", "password": "wrongpass"}).status_code == 401


def test_registration_validation_and_authentication_errors(client):
    assert client.post("/api/auth/register", json={"email": "bad", "password": "short"}).status_code == 400
    assert client.post("/api/auth/register", json=[]).status_code == 400
    assert client.get("/api/tasks").status_code == 401
    assert client.get("/api/tasks", headers={"Authorization": "Bearer bad"}).status_code == 401


def test_task_crud_and_defaults(client):
    register(client)
    headers = auth(client)
    created = client.post("/api/tasks", headers=headers, json={"title": "Ship API", "category": "work", "priority": "high", "due_date": "2026-09-01"})
    assert created.status_code == 201
    task = created.json["task"]
    assert task["status"] == "todo" and task["assigned_to"] is None
    task_id = task["id"]
    assert client.get(f"/api/tasks/{task_id}", headers=headers).json["task"]["title"] == "Ship API"
    updated = client.patch(f"/api/tasks/{task_id}", headers=headers, json={"status": "done", "description": "released"})
    assert updated.status_code == 200 and updated.json["task"]["status"] == "done"
    assert client.put(f"/api/tasks/{task_id}", headers=headers, json={"priority": "low"}).status_code == 200
    assert client.delete(f"/api/tasks/{task_id}", headers=headers).status_code == 204
    assert client.get(f"/api/tasks/{task_id}", headers=headers).status_code == 404


def test_task_validation_and_assignee(client):
    register(client)
    register(client, "bob@example.com")
    headers = auth(client)
    bob_id = client.post("/api/auth/login", json={"email": "bob@example.com", "password": "password123"}).json["user"]["id"]
    payload = {"title": "Assigned", "assigned_to": bob_id, "status": "invalid", "priority": "medium"}
    assert client.post("/api/tasks", headers=headers, json=payload).status_code == 400
    payload["status"] = "todo"
    created = client.post("/api/tasks", headers=headers, json=payload)
    assert created.status_code == 201
    assert client.post("/api/tasks", headers=headers, json={"title": "x", "assigned_to": 999}).status_code == 400
    assert client.post("/api/tasks", headers=headers, json={"title": "x", "due_date": "tomorrow"}).status_code == 400
    assert client.post("/api/tasks", headers=headers, json={"title": "x", "unexpected": True}).status_code == 400


def test_assignee_can_read_but_not_modify(client):
    register(client)
    register(client, "bob@example.com")
    alice_headers = auth(client)
    bob_headers = auth(client, "bob@example.com")
    bob_id = client.post("/api/auth/login", json={"email": "bob@example.com", "password": "password123"}).json["user"]["id"]
    task_id = client.post("/api/tasks", headers=alice_headers, json={"title": "Shared", "assigned_to": bob_id}).json["task"]["id"]
    assert client.get(f"/api/tasks/{task_id}", headers=bob_headers).status_code == 200
    assert client.patch(f"/api/tasks/{task_id}", headers=bob_headers, json={"status": "done"}).status_code == 403
    assert client.get("/api/tasks", headers=bob_headers).json["total"] == 1


def test_search_filters_and_pagination(client):
    register(client)
    headers = auth(client)
    for i in range(5):
        response = client.post("/api/tasks", headers=headers, json={"title": f"Project {i}", "description": "needle" if i == 2 else "other", "category": "work" if i < 3 else "home", "priority": "high" if i == 2 else "low", "status": "done" if i == 2 else "todo"})
        assert response.status_code == 201
    result = client.get("/api/tasks?search=needle&status=done&category=work&priority=high", headers=headers)
    assert result.json["total"] == 1 and result.json["tasks"][0]["title"] == "Project 2"
    page = client.get("/api/tasks?page=2&per_page=2", headers=headers)
    assert page.json["total"] == 5 and len(page.json["tasks"]) == 2 and page.json["pages"] == 3
    assert client.get("/api/tasks?page=nope", headers=headers).status_code == 400


def test_missing_task_and_user_cascade(client):
    register(client)
    headers = auth(client)
    assert client.get("/api/tasks/999", headers=headers).status_code == 404
    task_id = client.post("/api/tasks", headers=headers, json={"title": "Owned"}).json["task"]["id"]
    with client.application.app_context():
        from app import get_db
        get_db().execute("DELETE FROM users WHERE id = 1")
        get_db().commit()
        assert get_db().execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone() is None
