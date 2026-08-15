import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.db import db
from app.models import User

PASSWORD = "password123"


@pytest.fixture()
def app(tmp_path):
    database_path = str(tmp_path / "test.db")
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE_PATH": database_path,
            "JWT_EXPIRY_SECONDS": 3600,
        }
    )
    yield application
    with application.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_client(app):
    client = app.test_client()
    register = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": PASSWORD},
    )
    assert register.status_code == 201
    token = register.get_json()["token"]
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client


@pytest.fixture()
def second_client(app):
    client = app.test_client()
    client.post(
        "/api/auth/register",
        json={"username": "bob", "email": "bob@example.com", "password": PASSWORD},
    )
    login = client.post("/api/auth/login", json={"identifier": "bob", "password": PASSWORD})
    token = login.get_json()["token"]
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client


@pytest.fixture()
def make_user(app):
    def _make(username, email=None):
        with app.app_context():
            user = User(username=username, email=email or f"{username}@example.com")
            user.set_password(PASSWORD)
            db.session.add(user)
            db.session.commit()
            return user
    return _make


@pytest.fixture()
def create_task(auth_client):
    def _create(payload):
        response = auth_client.post("/api/tasks", json=payload)
        assert response.status_code == 201
        return response.get_json()
    return _create
