import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db


@pytest.fixture()
def app():
    app = create_app(TestConfig)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_headers(client):
    """Register a user and return auth headers + user dict."""
    resp = client.post(
        "/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    token = resp.get_json()["access_token"]
    user = resp.get_json()["user"]
    return {"Authorization": f"Bearer {token}"}, user


@pytest.fixture()
def second_user(client):
    resp = client.post(
        "/auth/register",
        json={"username": "bob", "email": "bob@example.com", "password": "secret123"},
    )
    return resp.get_json()["user"]
