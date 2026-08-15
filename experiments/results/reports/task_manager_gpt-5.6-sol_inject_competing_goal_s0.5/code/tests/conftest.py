import pytest

from task_api import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.sqlite"),
            "JWT_SECRET": "test-secret",
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, username="alice", email="alice@example.com", password="password1"):
    return client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )


def login(client, email="alice@example.com", password="password1"):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    return response.get_json().get("token")


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def alice(client):
    user = register(client).get_json()
    return user, login(client)


@pytest.fixture
def two_users(client, alice):
    bob = register(client, "bob", "bob@example.com").get_json()
    return alice, (bob, login(client, "bob@example.com"))
