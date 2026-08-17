import os
import tempfile

import pytest

from app import create_app
from config import TestConfig


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    test_app = create_app(TestConfig, DATABASE_PATH=db_path)

    yield test_app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


def register_user(client, username="alice", email="alice@example.com", password="secret123"):
    return client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_token(client):
    resp = register_user(client)
    return resp.get_json()["token"]


@pytest.fixture
def other_user_token(client):
    resp = register_user(client, username="bob", email="bob@example.com", password="secret123")
    return resp.get_json()["token"]


@pytest.fixture
def user_id(client, user_token):
    resp = client.get("/api/auth/me", headers=auth_header(user_token))
    return resp.get_json()["user"]["id"]


@pytest.fixture
def other_user_id(client, other_user_token):
    resp = client.get("/api/auth/me", headers=auth_header(other_user_token))
    return resp.get_json()["user"]["id"]
