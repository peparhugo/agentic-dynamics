import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite"), "JWT_SECRET_KEY": "test-secret-key-with-at-least-32-bytes"})


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, email="owner@example.com", password="password123", name="Owner"):
    response = client.post("/api/auth/register", json={"email": email, "password": password, "name": name})
    return response.get_json()


@pytest.fixture
def auth_headers(client):
    return {"Authorization": f"Bearer {register(client)['token']}"}
