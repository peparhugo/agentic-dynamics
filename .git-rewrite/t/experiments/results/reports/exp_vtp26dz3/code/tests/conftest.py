import pytest

from app import create_app


@pytest.fixture()
def app():
    return create_app(
        {
            "TESTING": True,
            "JWT_SECRET": "test-secret",
            "USERS": {"alice": "correct-horse"},
            "RATE_LIMIT": 100,
        }
    )


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_headers(client):
    response = client.post(
        "/api/v1/auth/token",
        json={"username": "alice", "password": "correct-horse"},
    )
    return {"Authorization": f"Bearer {response.json['access_token']}"}
