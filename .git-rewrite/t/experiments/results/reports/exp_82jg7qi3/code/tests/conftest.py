import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "test.sqlite3"),
        "JWT_SECRET": "test-secret",
        "RATE_LIMIT": 100,
    })


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth(client):
    client.post("/api/v1/auth/register", json={"username": "alice", "password": "password123"})
    response = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password123"})
    return {"Authorization": f"Bearer {response.json['access_token']}"}
