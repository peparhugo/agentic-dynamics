import pytest
from app import create_app
from app.database import get_db, init_db


@pytest.fixture
def app():
    app = create_app(testing=True)
    app.config["TESTING"] = True

    with app.app_context():
        init_db()

    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(client):
    client.post("/api/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123",
    })
    resp = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "password123",
    })
    data = resp.get_json()
    return {"Authorization": f"Bearer {data['access_token']}"}


@pytest.fixture
def second_user_headers(client):
    client.post("/api/auth/register", json={
        "username": "otheruser",
        "email": "other@example.com",
        "password": "password123",
    })
    resp = client.post("/api/auth/login", json={
        "username": "otheruser",
        "password": "password123",
    })
    data = resp.get_json()
    return {"Authorization": f"Bearer {data['access_token']}"}


@pytest.fixture
def category_id(client, auth_headers):
    resp = client.post("/api/categories", json={
        "name": "Work",
        "color": "#FF0000",
    }, headers=auth_headers)
    return resp.get_json()["category"]["id"]


@pytest.fixture
def task_id(client, auth_headers, category_id):
    resp = client.post("/api/tasks", json={
        "title": "Test Task",
        "description": "A test task",
        "status": "todo",
        "priority": "high",
        "category_id": category_id,
        "due_date": "2026-12-31T23:59:59",
    }, headers=auth_headers)
    return resp.get_json()["task"]["id"]
