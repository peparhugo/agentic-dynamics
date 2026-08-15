import pytest

from app import create_app
from app.extensions import db as _db


@pytest.fixture()
def app():
    application = create_app("testing")
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    return _db


def register_user(client, username="alice", email="alice@example.com", password="password123"):
    return client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def user_alice(client):
    resp = register_user(client, "alice", "alice@example.com", "password123")
    data = resp.get_json()
    return {
        "user": data["user"],
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "headers": auth_header(data["access_token"]),
    }


@pytest.fixture()
def user_bob(client):
    resp = register_user(client, "bob", "bob@example.com", "password123")
    data = resp.get_json()
    return {
        "user": data["user"],
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "headers": auth_header(data["access_token"]),
    }
