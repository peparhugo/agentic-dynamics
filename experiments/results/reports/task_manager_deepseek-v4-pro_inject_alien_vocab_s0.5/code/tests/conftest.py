import os
import tempfile

import pytest

from app import create_app
from app.extensions import db
from app.models import User


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret-key"
    JWT_SECRET_KEY = "test-jwt-secret-key"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///test.db"
    JWT_ACCESS_TOKEN_EXPIRES = 3600
    JSON_SORT_KEYS = False


@pytest.fixture()
def app(tmp_path):
    db_path = tmp_path / "test.db"
    TestConfig.SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"

    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db_session(app):
    with app.app_context():
        yield db.session


def register_user(client, username="alice", email="alice@example.com", password="secret123"):
    return client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )


def login_user(client, identifier="alice", password="secret123"):
    return client.post(
        "/api/auth/login", json={"username": identifier, "password": password}
    )


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def get_token(client, username="alice", email="alice@example.com", password="secret123"):
    register_user(client, username=username, email=email, password=password)
    resp = login_user(client, identifier=username, password=password)
    return resp.get_json()["access_token"]
