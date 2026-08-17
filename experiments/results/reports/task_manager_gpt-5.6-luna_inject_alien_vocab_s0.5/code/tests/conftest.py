import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path):
    return create_app({"TESTING": True, "SECRET_KEY": "test-secret", "DATABASE": str(tmp_path / "test.sqlite")})


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, email="one@example.com", name="One"):
    response = client.post("/api/auth/register", json={"email": email, "name": name, "password": "password123"})
    return response


@pytest.fixture()
def auth(client):
    body = register(client).get_json()
    return {"Authorization": "Bearer " + body["token"]}


@pytest.fixture()
def second_user(client):
    return register(client, "two@example.com", "Two").get_json()
