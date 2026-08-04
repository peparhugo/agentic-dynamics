import pytest
from app import create_app, db
from app.config import TestConfig


@pytest.fixture
def app():
    app = create_app(TestConfig)
    app.config.update({"TESTING": True})
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def _db(app):
    with app.app_context():
        db.create_all()
        yield db
        db.drop_all()


@pytest.fixture
def auth_headers(client):
    client.post("/v1/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123",
    })
    resp = client.post("/v1/auth/login", json={
        "email": "test@example.com",
        "password": "password123",
    })
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers2(client):
    client.post("/v1/auth/register", json={
        "username": "otheruser",
        "email": "other@example.com",
        "password": "password123",
    })
    resp = client.post("/v1/auth/login", json={
        "email": "other@example.com",
        "password": "password123",
    })
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
