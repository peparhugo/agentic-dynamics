import pytest

from task_api import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.sqlite"),
            "JWT_SECRET": "test-secret",
            "JWT_TTL_SECONDS": 3600,
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def register(client):
    def make_user(name="Alice", email="alice@example.com", password="password123"):
        response = client.post(
            "/auth/register",
            json={"name": name, "email": email, "password": password},
        )
        assert response.status_code == 201
        login = client.post("/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200
        return response.get_json()["user"], login.get_json()["access_token"]

    return make_user


@pytest.fixture
def user(register):
    return register()


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}
