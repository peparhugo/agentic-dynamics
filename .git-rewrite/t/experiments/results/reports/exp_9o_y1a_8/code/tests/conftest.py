import pytest

from app import create_app
from app.config import TestConfig
from app.models import db as _db


@pytest.fixture(scope="session")
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
    yield app


@pytest.fixture(scope="function")
def db(app):
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.rollback()
        _db.drop_all()


@pytest.fixture
def client(app, db):
    return app.test_client()


@pytest.fixture
def runner(app, db):
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
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def second_user_headers(client):
    client.post("/api/auth/register", json={
        "username": "seconduser",
        "email": "second@example.com",
        "password": "password123",
    })
    resp = client.post("/api/auth/login", json={
        "username": "seconduser",
        "password": "password123",
    })
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def category(client, auth_headers):
    resp = client.post(
        "/api/categories",
        json={"name": "Work", "description": "Work tasks"},
        headers=auth_headers,
    )
    return resp.get_json()


@pytest.fixture
def task(client, auth_headers, category):
    resp = client.post(
        "/api/tasks",
        json={
            "title": "Test Task",
            "description": "A test task",
            "priority": "high",
            "status": "pending",
            "category_id": category["id"],
        },
        headers=auth_headers,
    )
    return resp.get_json()
