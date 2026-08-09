import pytest

from app import create_app


@pytest.fixture()
def app():
    return create_app(
        {
            "TESTING": True,
            "JWT_SECRET": "test-secret",
            "RATE_LIMIT_REQUESTS": 100,
            "RATE_LIMIT_STORE": {},
            "AUDIT_LOG": [],
        }
    )


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def token(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password"})
    return response.get_json()["access_token"]


@pytest.fixture()
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}
