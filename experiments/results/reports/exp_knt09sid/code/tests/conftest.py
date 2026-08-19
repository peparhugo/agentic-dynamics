import pytest
from app import create_app


@pytest.fixture()
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite"), "SECRET_KEY": "test-secret"})


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, username="alice", email="alice@example.com"):
    response = client.post("/api/auth/register", json={"username": username, "email": email, "password": "password123"})
    return response.get_json()


@pytest.fixture()
def auth(client):
    return {"Authorization": "Bearer " + register(client)["token"]}
