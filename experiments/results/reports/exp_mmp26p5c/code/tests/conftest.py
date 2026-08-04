import pytest
from app import create_app, db as _db
from app.config import TestConfig
from app.models import User, Item


@pytest.fixture
def app():
    app = create_app("app.config.TestConfig")
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
def registered_user(client, app):
    with app.app_context():
        resp = client.post("/api/v1/auth/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
        })
        data = resp.get_json()
    return data
