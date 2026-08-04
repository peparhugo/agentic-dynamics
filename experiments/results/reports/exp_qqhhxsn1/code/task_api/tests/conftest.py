import pytest
from app import create_app
from app.extensions import db as _db
from app.models import User, Task
from config import TestConfig


@pytest.fixture
def app():
    _app = create_app(config_class=TestConfig)
    with _app.app_context():
        _db.create_all()
    yield _app
    with _app.app_context():
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    with app.app_context():
        yield _db


def _register_user(client, username="testuser", email="test@example.com", password="password123"):
    resp = client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    return resp


def _login_user(client, identifier="testuser", password="password123"):
    resp = client.post(
        "/api/auth/login",
        json={"username": identifier, "password": password},
    )
    return resp


def _auth_headers(client):
    resp = _register_user(client)
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers(client):
    return _auth_headers(client)


@pytest.fixture
def auth_user_id(client, auth_headers):
    resp = client.get("/api/auth/me", headers=auth_headers)
    return resp.get_json()["user"]["id"]
