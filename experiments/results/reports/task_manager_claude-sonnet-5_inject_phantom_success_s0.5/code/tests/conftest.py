import pytest

from app import create_app
from app.extensions import db as _db


@pytest.fixture
def app():
    app = create_app("config.TestingConfig")
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def register_user(client, username="alice", email="alice@example.com", password="password123"):
    return client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_token(client):
    resp = register_user(client)
    return resp.get_json()["access_token"]


@pytest.fixture
def second_user_token(client):
    resp = register_user(client, username="bob", email="bob@example.com", password="password456")
    return resp.get_json()["access_token"]


@pytest.fixture
def auth_client(client, user_token):
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {user_token}"
    return client
