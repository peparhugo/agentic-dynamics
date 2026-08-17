import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db


@pytest.fixture
def app():
    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def register():
    def _register(client, username, email=None, password="password123"):
        email = email or f"{username}@example.com"
        return client.post(
            "/auth/register",
            json={"username": username, "email": email, "password": password},
        )

    return _register


@pytest.fixture
def auth():
    def _auth(client, username, password="password123"):
        resp = client.post(
            "/auth/login", json={"username": username, "password": password}
        )
        assert resp.status_code == 200, resp.get_json()
        token = resp.get_json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _auth


@pytest.fixture
def register_and_auth(register, auth):
    def _register_and_auth(client, username, email=None, password="password123"):
        register(client, username, email, password)
        return auth(client, username, password)

    return _register_and_auth
