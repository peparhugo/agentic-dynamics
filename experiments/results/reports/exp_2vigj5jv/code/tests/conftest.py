import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "SECRET_KEY": "test-secret-key-with-at-least-32-bytes", "DATABASE": str(tmp_path / "test.sqlite")})


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, username="alice", email=None, password="password123"):
    email = email or f"{username}@example.com"
    response = client.post("/api/auth/register", json={"username": username, "email": email, "password": password})
    return response


def token(client, username="alice"):
    response = register(client, username)
    return response.get_json()["token"]


@pytest.fixture
def auth(client):
    return {"Authorization": f"Bearer {token(client)}"}
