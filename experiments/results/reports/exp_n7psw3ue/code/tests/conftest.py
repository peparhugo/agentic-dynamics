import pytest

from app import create_app, db
from app.auth import hash_password
from app.config import TestConfig
from app.models import Item, User
from app.rate_limit import rate_limiter


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    rate_limiter.reset()
    yield


@pytest.fixture
def auth_headers(client):
    client.post(
        "/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
        },
    )
    resp = client.post(
        "/v1/auth/login",
        json={"username": "testuser", "password": "password123"},
    )
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_user_headers(client):
    client.post(
        "/v1/auth/register",
        json={
            "username": "otheruser",
            "email": "other@example.com",
            "password": "password123",
        },
    )
    resp = client.post(
        "/v1/auth/login",
        json={"username": "otheruser", "password": "password123"},
    )
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
