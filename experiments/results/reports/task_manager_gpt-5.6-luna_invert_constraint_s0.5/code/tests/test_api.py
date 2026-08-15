from .conftest import register


def test_register_login_and_me(client):
    result = register(client)
    assert result["user"]["username"] == "alice"
    assert client.post("/api/auth/register", json={"username": "alice", "email": "other@example.com", "password": "password123"}).status_code == 409
    login = client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    assert login.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": "Bearer " + login.get_json()["token"]})
    assert me.get_json()["user"]["email"] == "alice@example.com"


def test_auth_required(client):
    assert client.get("/api/tasks").status_code == 401
    assert client.post("/api/auth/register", json={"username": "a", "email": "bad", "password": "short"}).status_code == 400


def test_categories_and_task_crud(client, auth):
    category = client.post("/api/categories", headers=auth, json={"name": "Work"}).get_json()["category"]
    created = client.post("/api/tasks", headers=auth, json={"title": "Ship API", "description": "write docs", "category_id": category["id"], "priority": "high", "due_date": "2030-01-01"})
    assert created.status_code == 201
    task = created.get_json()["task"]
    assert task["category"] == "Work"
    assert client.get(f"/api/tasks/{task['id']}", headers=auth).status_code == 200
    updated = client.patch(f"/api/tasks/{task['id']}", headers=auth, json={"status": "completed"})
    assert updated.get_json()["task"]["status"] == "completed"
    assert client.delete(f"/api/tasks/{task['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/tasks/{task['id']}", headers=auth).status_code == 404


def test_assignment_visibility_and_permissions(client, auth):
    bob = register(client, "bob", "bob@example.com")
    task = client.post("/api/tasks", headers=auth, json={"title": "Shared", "assigned_to": bob["user"]["id"]}).get_json()["task"]
    bob_headers = {"Authorization": "Bearer " + bob["token"]}
    assert client.get(f"/api/tasks/{task['id']}", headers=bob_headers).status_code == 200
    assert client.patch(f"/api/tasks/{task['id']}", headers=bob_headers, json={"title": "No"}).status_code == 404


def test_filters_search_and_pagination(client, auth):
    for title, priority in [("alpha", "urgent"), ("beta", "low"), ("alphabet", "urgent")]:
        client.post("/api/tasks", headers=auth, json={"title": title, "priority": priority})
    response = client.get("/api/tasks?q=alpha&priority=urgent&per_page=1", headers=auth)
    data = response.get_json()
    assert data["pagination"] == {"page": 1, "per_page": 1, "total": 2, "pages": 2}
    assert len(data["tasks"]) == 1
