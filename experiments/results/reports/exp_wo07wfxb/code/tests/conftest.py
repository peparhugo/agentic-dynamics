import pytest
from app import create_app
from app.models.user import reset_store


@pytest.fixture
def app():
    app = create_app("config.TestConfig")
    app.config.update({"TESTING": True})
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_store():
    reset_store()
    yield
    reset_store()


@pytest.fixture
def auth_headers(client):
    client.post(
        "/api/v1/auth/register",
        json={"username": "tester", "password": "password123"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "tester", "password": "password123"},
    )
    token = resp.get_json()["access_token"]
    yield {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_2(client):
    client.post(
        "/api/v1/auth/register",
        json={"username": "tester2", "password": "password123"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "tester2", "password": "password123"},
    )
    token = resp.get_json()["access_token"]
    yield {"Authorization": f"Bearer {token}"}
