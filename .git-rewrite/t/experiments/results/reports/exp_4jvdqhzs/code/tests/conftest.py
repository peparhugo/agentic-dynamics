import pytest

from app import create_app


@pytest.fixture()
def app():
    return create_app({"TESTING": True, "JWT_SECRET": "test-secret", "RATE_LIMIT": 1000})


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_headers(client):
    credentials = {"username": "alice", "password": "password123"}
    client.post("/api/v1/auth/register", json=credentials)
    response = client.post("/api/v1/auth/login", json=credentials)
    token = response.get_json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}
