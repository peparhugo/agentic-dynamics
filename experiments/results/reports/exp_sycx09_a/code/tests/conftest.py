import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db"), "SECRET_KEY": "test-secret", "JWT_EXPIRATION_SECONDS": 3600})


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, email="owner@example.com", password="password123", name="Owner"):
    return client.post("/api/auth/register", json={"email": email, "password": password, "name": name})


@pytest.fixture
def auth(client):
    response = register(client)
    return {"Authorization": f"Bearer {response.get_json()['token']}"}
