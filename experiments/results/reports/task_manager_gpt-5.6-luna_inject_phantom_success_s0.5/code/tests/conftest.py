import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite"), "SECRET_KEY": "test-secret"})


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, email="alice@example.com", password="password123", name="Alice"):
    response = client.post("/api/auth/register", json={"email": email, "password": password, "name": name})
    return response


@pytest.fixture
def auth_client(client):
    response = register(client)
    token = response.get_json()["token"]
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client
