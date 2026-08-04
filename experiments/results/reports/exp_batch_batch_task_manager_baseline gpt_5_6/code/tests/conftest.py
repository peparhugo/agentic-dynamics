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


@pytest.fixture
def register(client):
    def register_user(username="alice", email="alice@example.com", password="password1"):
        return client.post(
            "/api/auth/register",
            json={"username": username, "email": email, "password": password},
        )

    return register_user


@pytest.fixture
def auth(register):
    response = register()
    return {
        "headers": {"Authorization": f"Bearer {response.json['token']}"},
        "user": response.json["user"],
    }


@pytest.fixture
def second_auth(register):
    response = register("bob", "bob@example.com")
    return {
        "headers": {"Authorization": f"Bearer {response.json['token']}"},
        "user": response.json["user"],
    }


@pytest.fixture
def category(client, auth):
    return client.post("/api/categories", json={"name": "Work"}, headers=auth["headers"]).json[
        "category"
    ]
