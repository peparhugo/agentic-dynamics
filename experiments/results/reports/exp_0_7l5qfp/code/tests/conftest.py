import pytest

from app import create_app, init_db


@pytest.fixture
def app(tmp_path):
    application = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite3"), "SECRET_KEY": "test-secret"})
    init_db(application)
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, email="alice@example.com", password="password123"):
    response = client.post("/api/auth/register", json={"email": email, "password": password})
    return response


def auth(client, email="alice@example.com", password="password123"):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {response.json['token']}"}
