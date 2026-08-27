import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import User, Item


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    yield app


@pytest.fixture()
def client(app):
    with app.test_client() as client:
        yield client


def _register(client, username="alice", email="alice@example.com", password="password123"):
    return client.post(
        "/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )


@pytest.fixture()
def user(client):
    resp = _register(client)
    assert resp.status_code == 201
    return resp.get_json()


@pytest.fixture()
def tokens(client, user):
    resp = client.post(
        "/v1/auth/login",
        json={"username": "alice", "password": "password123"},
    )
    assert resp.status_code == 200
    return resp.get_json()


@pytest.fixture()
def auth_headers(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}
