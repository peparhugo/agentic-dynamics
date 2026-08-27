import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db


@pytest.fixture()
def app():
    application = create_app(TestConfig)
    application.config.update(TESTING=True)
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


def register_user(client, email="user@example.com", password="password123"):
    return client.post(
        "/v1/auth/register",
        json={"email": email, "password": password},
    )


def login_user(client, email="user@example.com", password="password123"):
    return client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    )


def auth_headers(client, email="user@example.com", password="password123"):
    resp = register_user(client, email, password)
    tokens = resp.get_json()
    access_token = tokens["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture()
def user_headers(client):
    return auth_headers(client)
