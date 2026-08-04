import os
import tempfile
import pytest
from app_factory import create_app
from app import init_db


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    app = create_app({
        "TESTING": True,
        "DATABASE": db_path,
        "SECRET_KEY": "test-secret",
        "JWT_SECRET_KEY": "test-jwt-secret",
        "JWT_ACCESS_TOKEN_EXPIRES": 3600,
    })

    yield app

    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


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
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def second_user(client):
    resp = client.post("/api/auth/register", json={
        "username": "user2",
        "email": "user2@example.com",
        "password": "password123",
    })
    return resp.get_json()


@pytest.fixture
def created_task(client, auth_headers):
    resp = client.post("/api/tasks", json={
        "title": "Test task",
        "description": "Test description",
        "status": "pending",
        "priority": "high",
        "category": "testing",
        "due_date": "2026-12-31",
    }, headers=auth_headers)
    assert resp.status_code == 201
    return resp.get_json()["task"]
