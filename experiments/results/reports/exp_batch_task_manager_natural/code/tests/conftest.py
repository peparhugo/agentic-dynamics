import pytest

from app import create_app
from config import TestConfig
from models import db as _db


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
    yield app
    with app.app_context():
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    with app.app_context():
        yield _db


@pytest.fixture
def user(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "testuser", "email": "test@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    return data["user"], data["token"]


@pytest.fixture
def user2(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "otheruser", "email": "other@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    return data["user"], data["token"]


@pytest.fixture
def auth_header(user):
    _, token = user
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_header2(user2):
    _, token = user2
    return {"Authorization": f"Bearer {token}"}


def _make_task(client, auth_header, **kwargs):
    defaults = {
        "title": "Test Task",
        "description": "A test task",
        "status": "todo",
        "priority": "medium",
        "category": "testing",
    }
    defaults.update(kwargs)
    resp = client.post("/api/tasks", json=defaults, headers=auth_header)
    assert resp.status_code == 201
    return resp.get_json()["task"]
