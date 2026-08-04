import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def auth_headers(client):
    client.post(
        "/v1/auth/register",
        json={"username": "testuser", "email": "test@example.com", "password": "password123"},
    )
    resp = client.post(
        "/v1/auth/login",
        json={"email": "test@example.com", "password": "password123"},
    )
    data = resp.get_json()
    return {
        "Authorization": f"Bearer {data['access_token']}",
        "refresh_token": data["refresh_token"],
    }
