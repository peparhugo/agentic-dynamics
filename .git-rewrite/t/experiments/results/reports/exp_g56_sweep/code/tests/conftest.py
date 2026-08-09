import pytest

from app import create_app
from app.models import Base


@pytest.fixture
def app():
    application = create_app(
        {
            "TESTING": True,
            "DATABASE_URL": "sqlite://",
            "JWT_SECRET": "test-secret",
            "ACCESS_TOKEN_TTL": 300,
            "REFRESH_TOKEN_TTL": 3600,
        }
    )
    yield application
    application.extensions["db_session"].remove()
    Base.metadata.drop_all(application.extensions["db_engine"])


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth(client):
    response = client.post(
        "/v1/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    )
    body = response.get_json()
    return {
        "access": body["access_token"],
        "refresh": body["refresh_token"],
        "headers": {"Authorization": f"Bearer {body['access_token']}"},
    }
