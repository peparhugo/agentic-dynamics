import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite"), "JWT_SECRET": "test-secret-key-must-be-at-least-32"})


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, username="alice", password="password123"):
    return client.post("/auth/register", json={"username": username, "password": password})


@pytest.fixture
def auth(client):
    register(client)
    response = client.post("/auth/login", json={"username": "alice", "password": "password123"})
    return {"Authorization": f"Bearer {response.get_json()['access_token']}"}
