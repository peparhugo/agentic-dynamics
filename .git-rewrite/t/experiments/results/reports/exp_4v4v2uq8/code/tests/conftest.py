import pytest
from src.app import create_app
from src.config import TestConfig
from src.models.user import user_store
from src.middleware.rate_limit import _rate_store


@pytest.fixture(autouse=True)
def clean_store():
    user_store.clear()
    _rate_store.clear()
    yield
    user_store.clear()
    _rate_store.clear()


@pytest.fixture
def app():
    app = create_app(TestConfig)
    app.config.update({"TESTING": True})
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def sample_user(client):
    resp = client.post(
        "/api/v1/users",
        json={"username": "testuser", "email": "test@example.com", "password": "password123"},
    )
    return resp.get_json()


@pytest.fixture
def auth_token(client, sample_user):
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "password123"},
    )
    return resp.get_json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def admin_user(client):
    resp = client.post(
        "/api/v1/users",
        json={
            "username": "adminuser",
            "email": "admin@example.com",
            "password": "adminpass123",
            "role": "admin",
        },
    )
    return resp.get_json()


@pytest.fixture
def admin_token(client, admin_user):
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "adminuser", "password": "adminpass123"},
    )
    return resp.get_json()["access_token"]


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
