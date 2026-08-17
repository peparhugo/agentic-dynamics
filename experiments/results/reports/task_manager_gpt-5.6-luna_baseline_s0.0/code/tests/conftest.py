import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "SECRET_KEY": "test-secret", "DATABASE": str(tmp_path / "test.sqlite")})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth(client):
    response = client.post("/api/auth/register", json={"username": "alice", "email": "alice@example.com", "password": "password123"})
    return {"Authorization": "Bearer " + response.get_json()["token"]}


def register(client, username="bob", email="bob@example.com"):
    return client.post("/api/auth/register", json={"username": username, "email": email, "password": "password123"})
