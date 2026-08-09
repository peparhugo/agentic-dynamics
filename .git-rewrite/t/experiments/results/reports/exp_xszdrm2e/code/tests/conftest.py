import pytest
from app import create_app
from app.config import TestConfig


@pytest.fixture
def app():
    app = create_app(config_class=TestConfig)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "password123", "name": "Test"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "password123"},
    )
    tokens = resp.get_json()["tokens"]
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def admin_headers(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@example.com",
            "password": "password123",
            "name": "Admin",
            "role": "admin",
        },
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )
    tokens = resp.get_json()["tokens"]
    return {"Authorization": f"Bearer {tokens['access_token']}"}
