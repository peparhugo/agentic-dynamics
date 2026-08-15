import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path):
    return create_app({"TESTING": True, "SECRET_KEY": "test-secret", "DATABASE": str(tmp_path / "test.sqlite")})


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, username="alice", email="alice@example.com", password="password123"):
    response = client.post("/api/auth/register", json={"username": username, "email": email, "password": password})
    return response


def token(client, username="alice", email="alice@example.com"):
    register(client, username, email)
    return client.post("/api/auth/login", json={"username": username, "password": "password123"}).get_json()["token"]


@pytest.fixture()
def auth(client):
    value = token(client)
    return {"Authorization": f"Bearer {value}"}
