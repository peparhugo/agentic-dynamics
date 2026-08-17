from app import create_app

from .conftest import register


def test_registration_login_and_me(client):
    response = register(client)
    assert response.status_code == 201
    body = response.get_json()
    assert body["user"]["email"] == "one@example.com"
    assert body["token"]
    login = client.post("/api/auth/login", json={"email": "ONE@example.com", "password": "password123"})
    assert login.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": "Bearer " + login.get_json()["token"]})
    assert me.status_code == 200
    assert me.get_json()["user"]["name"] == "One"


def test_auth_validation_duplicate_and_invalid_login(client):
    assert client.post("/api/auth/register", json={"email": "x", "name": "X", "password": "short"}).status_code == 400
    assert register(client).status_code == 201
    assert register(client).status_code == 409
    assert client.post("/api/auth/login", json={"email": "one@example.com", "password": "wrongpass"}).status_code == 401
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer bad"}).status_code == 401


def test_categories_and_task_crud(client, auth, second_user):
    category = client.post("/api/categories", headers=auth, json={"name": "Work"})
    assert category.status_code == 201
    category_id = category.get_json()["category"]["id"]
    assert client.post("/api/categories", headers=auth, json={"name": "work"}).status_code == 409
    assert client.get("/api/categories", headers=auth).get_json()["categories"][0]["name"] == "Work"
    task = client.post("/api/tasks", headers=auth, json={"title": "Ship feature", "description": "Write tests", "priority": "high", "due_date": "2030-01-02", "category_id": category_id, "assigned_to": second_user["user"]["id"]})
    assert task.status_code == 201
    task_id = task.get_json()["task"]["id"]
    item = client.get(f"/api/tasks/{task_id}", headers=auth).get_json()["task"]
    assert item["category"]["name"] == "Work"
    assert item["assignee"]["email"] == "two@example.com"
    update = client.patch(f"/api/tasks/{task_id}", headers=auth, json={"status": "done", "title": "Shipped"})
    assert update.status_code == 200
    assert update.get_json()["task"]["status"] == "done"
    assert client.delete(f"/api/tasks/{task_id}", headers=auth).status_code == 204
    assert client.get(f"/api/tasks/{task_id}", headers=auth).status_code == 404


def test_task_validation_and_relationships(client, auth):
    assert client.post("/api/tasks", headers=auth, json={}).status_code == 400
    assert client.post("/api/tasks", headers=auth, json={"title": "x", "status": "bad"}).status_code == 400
    assert client.post("/api/tasks", headers=auth, json={"title": "x", "priority": "bad"}).status_code == 400
    assert client.post("/api/tasks", headers=auth, json={"title": "x", "due_date": "tomorrow"}).status_code == 400
    assert client.post("/api/tasks", headers=auth, json={"title": "x", "category_id": 999}).status_code == 400
    assert client.post("/api/tasks", headers=auth, json={"title": "x", "assigned_to": 999}).status_code == 400
    assert client.post("/api/categories", headers=auth, json={}).status_code == 400


def test_filter_search_and_pagination(client, auth):
    category = client.post("/api/categories", headers=auth, json={"name": "Personal"}).get_json()["category"]["id"]
    for i in range(5):
        response = client.post("/api/tasks", headers=auth, json={"title": f"Task {i}", "description": "needle" if i == 2 else "other", "status": "done" if i < 3 else "todo", "priority": "high" if i == 2 else "low", "category_id": category})
        assert response.status_code == 201
    response = client.get("/api/tasks?page=1&per_page=2&status=done&priority=high&category=Personal&search=needle", headers=auth)
    body = response.get_json()
    assert response.status_code == 200
    assert body["pagination"] == {"page": 1, "per_page": 2, "total": 1, "pages": 1}
    assert body["tasks"][0]["title"] == "Task 2"
    second = client.get("/api/tasks?page=2&per_page=2", headers=auth).get_json()
    assert second["pagination"]["total"] == 5
    assert len(second["tasks"]) == 2


def test_users_cannot_access_each_others_tasks(client, auth, second_user):
    created = client.post("/api/tasks", headers=auth, json={"title": "Private"}).get_json()["task"]["id"]
    other_token = client.post("/api/auth/login", json={"email": "two@example.com", "password": "password123"}).get_json()["token"]
    other = {"Authorization": "Bearer " + other_token}
    assert client.get(f"/api/tasks/{created}", headers=other).status_code == 404
    assert client.patch(f"/api/tasks/{created}", headers=other, json={"title": "stolen"}).status_code == 404
    assert client.delete(f"/api/tasks/{created}", headers=other).status_code == 404
    assert client.get("/api/tasks", headers=other).get_json()["pagination"]["total"] == 0
