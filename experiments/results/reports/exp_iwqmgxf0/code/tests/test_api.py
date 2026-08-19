import base64
import json

import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db"), "JWT_SECRET": "test-secret"})


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, username="alice", password="password123"):
    return client.post("/auth/register", json={"username": username, "password": password})


def token(client, username="alice", password="password123"):
    register(client, username, password)
    return client.post("/auth/login", json={"username": username, "password": password}).json["access_token"]


def auth(value):
    return {"Authorization": f"Bearer {value}"}


def test_registration_and_login(client):
    response = register(client)
    assert response.status_code == 201
    assert response.json["user"]["username"] == "alice"
    assert register(client).status_code == 409
    response = client.post("/auth/login", json={"username": "alice", "password": "password123"})
    assert response.status_code == 200
    assert response.json["token_type"] == "Bearer"


def test_authentication_rejects_invalid_credentials_and_tokens(client):
    register(client)
    assert client.post("/auth/login", json={"username": "alice", "password": "wrongpass"}).status_code == 401
    assert client.get("/tasks").status_code == 401
    assert client.get("/tasks", headers=auth("invalid")).status_code == 401


def test_registration_validation(client):
    assert client.post("/auth/register", json={"username": "ab", "password": "password123"}).status_code == 400
    assert client.post("/auth/register", json={"username": "valid", "password": "short"}).status_code == 400
    assert client.post("/auth/register", data="not json").status_code == 400


def test_category_creation_and_listing(client):
    access_token = token(client)
    response = client.post("/categories", json={"name": "Work"}, headers=auth(access_token))
    assert response.status_code == 201
    assert response.json["category"]["name"] == "Work"
    assert client.post("/categories", json={"name": "work"}, headers=auth(access_token)).status_code == 409
    response = client.get("/categories", headers=auth(access_token))
    assert [category["name"] for category in response.json["categories"]] == ["Work"]


def test_task_crud_with_assignment_and_category(client):
    owner_token = token(client)
    category = client.post("/categories", json={"name": "Home"}, headers=auth(owner_token)).json["category"]
    register(client, "bob")
    bob_login = client.post("/auth/login", json={"username": "bob", "password": "password123"}).json
    # The task owner can assign any registered user.
    response = client.post("/tasks", headers=auth(owner_token), json={
        "title": "Buy milk", "description": "Two cartons", "priority": "high", "status": "todo",
        "due_date": "2026-12-01T10:00:00Z", "category_id": category["id"], "assignee_id": 2,
    })
    assert response.status_code == 201
    task = response.json["task"]
    assert task["category_name"] == "Home" and task["assignee_username"] == "bob"
    response = client.patch(f"/tasks/{task['id']}", headers=auth(owner_token), json={"status": "done", "due_date": None})
    assert response.status_code == 200 and response.json["task"]["status"] == "done"
    assert client.get(f"/tasks/{task['id']}", headers=auth(bob_login["access_token"])).status_code == 404
    assert client.delete(f"/tasks/{task['id']}", headers=auth(owner_token)).status_code == 204
    assert client.get(f"/tasks/{task['id']}", headers=auth(owner_token)).status_code == 404


def test_task_validation_and_authorization(client):
    access_token = token(client)
    headers = auth(access_token)
    assert client.post("/tasks", headers=headers, json={}).status_code == 400
    assert client.post("/tasks", headers=headers, json={"title": "x", "priority": "urgent"}).status_code == 400
    assert client.post("/tasks", headers=headers, json={"title": "x", "due_date": "soon"}).status_code == 400
    task = client.post("/tasks", headers=headers, json={"title": "x"}).json["task"]
    assert client.patch(f"/tasks/{task['id']}", headers=headers, json={"status": "invalid"}).status_code == 400
    assert client.patch(f"/tasks/{task['id']}", headers=headers, json={}).status_code == 400


def test_categories_are_private_to_their_owner(client):
    alice_token = token(client)
    alice_headers = auth(alice_token)
    private_category = client.post("/categories", headers=alice_headers, json={"name": "Personal"}).json["category"]
    bob_token = token(client, "bob")
    bob_headers = auth(bob_token)
    assert client.get("/categories", headers=bob_headers).json["categories"] == []
    assert client.post("/categories", headers=bob_headers, json={"name": "Personal"}).status_code == 201
    response = client.post("/tasks", headers=bob_headers, json={"title": "Private", "category_id": private_category["id"]})
    assert response.status_code == 400


def test_task_filters_search_and_pagination(client):
    access_token = token(client)
    headers = auth(access_token)
    category = client.post("/categories", headers=headers, json={"name": "Work"}).json["category"]
    for title, status, priority, category_id in [
        ("Write report", "todo", "high", category["id"]),
        ("Read book", "done", "low", None),
        ("Review report", "todo", "medium", category["id"]),
    ]:
        assert client.post("/tasks", headers=headers, json={"title": title, "status": status, "priority": priority, "category_id": category_id}).status_code == 201
    response = client.get("/tasks?status=todo&category_id=1&search=report&per_page=1", headers=headers)
    assert response.status_code == 200
    assert response.json["total"] == 2 and len(response.json["tasks"]) == 1
    assert client.get("/tasks?priority=low", headers=headers).json["total"] == 1
    assert client.get("/tasks?page=0", headers=headers).status_code == 400
    assert client.get("/tasks?status=bad", headers=headers).status_code == 400


def test_tampered_token_is_rejected(client):
    access_token = token(client)
    encoded, _signature = access_token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    payload["sub"] = 999
    tampered = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode() + ".bad"
    assert client.get("/tasks", headers=auth(tampered)).status_code == 401
