import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import bcrypt, db
from app.models import Category, User


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


def _create_user(app, username, email, password="password123"):
    with app.app_context():
        user = User(
            username=username,
            email=email,
            password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
        )
        db.session.add(user)
        db.session.commit()
        return user.id


@pytest.fixture()
def user_id(app):
    return _create_user(app, "alice", "alice@example.com")


@pytest.fixture()
def second_user_id(app):
    return _create_user(app, "bob", "bob@example.com")


@pytest.fixture()
def auth_headers(app, client, user_id):
    resp = client.post(
        "/api/auth/login", json={"username": "alice", "password": "password123"}
    )
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def second_auth_headers(app, client, second_user_id):
    resp = client.post(
        "/api/auth/login", json={"username": "bob", "password": "password123"}
    )
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def category(app, auth_headers, client):
    resp = client.post(
        "/api/categories",
        json={"name": "Work", "description": "Work related"},
        headers=auth_headers,
    )
    return resp.get_json()
