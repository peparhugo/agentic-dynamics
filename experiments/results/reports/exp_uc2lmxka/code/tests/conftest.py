import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.sqlite"),
            "JWT_SECRET": "test-secret",
            "RATE_LIMIT": 100,
        }
    )


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_headers(client):
    client.post("/api/v1/auth/register", json={"email": "user@example.com", "password": "password123"})
    response = client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "password123"})
    return {"Authorization": f"Bearer {response.get_json()['access_token']}"}
