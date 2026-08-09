import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE": str(tmp_path / "test.db"),
            "RATE_LIMIT": 1000,
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth(client):
    def authenticate(username="alice", password="password123"):
        client.post("/api/v1/auth/register", json={"username": username, "password": password})
        response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
        return {"Authorization": f"Bearer {response.json['access_token']}"}

    return authenticate
