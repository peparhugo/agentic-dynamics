import pytest

from app import create_app
from app.extensions import db as _db


@pytest.fixture
def app():
    application = create_app("testing")
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    return _db


def register_user(client, username="alice", email="alice@example.com", password="password123"):
    return client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )


@pytest.fixture
def user_factory(client):
    def _create(username="alice", email="alice@example.com", password="password123"):
        resp = register_user(client, username, email, password)
        assert resp.status_code == 201, resp.get_json()
        body = resp.get_json()
        return body["user"], body["access_token"]

    return _create


@pytest.fixture
def auth_user(user_factory):
    user, token = user_factory()
    return user, token


@pytest.fixture
def auth_headers(auth_user):
    _, token = auth_user
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def second_user(user_factory):
    user, token = user_factory(username="bob", email="bob@example.com", password="password456")
    return user, token


@pytest.fixture
def second_auth_headers(second_user):
    _, token = second_user
    return {"Authorization": f"Bearer {token}"}
