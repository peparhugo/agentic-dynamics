import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db

from tests.helpers import register_user, login  # noqa: F401


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    return _db


@pytest.fixture()
def user(client):
    resp = register_user(client)
    assert resp.status_code == 201
    token = resp.get_json()["token"]
    return {"username": "alice", "email": "alice@example.com",
            "password": "password123", "token": token}


@pytest.fixture()
def second_user(client):
    resp = register_user(client, username="bob", email="bob@example.com",
                         password="password456")
    assert resp.status_code == 201
    token = resp.get_json()["token"]
    return {"username": "bob", "email": "bob@example.com",
            "password": "password456", "token": token, "id": resp.get_json()["user"]["id"]}


@pytest.fixture()
def auth_headers(user):
    return {"Authorization": f"Bearer {user['token']}"}


@pytest.fixture()
def category(client, auth_headers):
    resp = client.post("/api/categories", json={"name": "Work", "color": "#ff0000"},
                       headers=auth_headers)
    assert resp.status_code == 201
    return resp.get_json()["category"]
