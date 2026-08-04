import pytest

from app import create_app, db


@pytest.fixture()
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_SECRET_KEY": "test-secret",
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, username="alice", email=None, password="password123"):
    email = email or f"{username}@example.com"
    return client.post("/api/auth/register", json={
        "username": username, "email": email, "password": password})


def login(client, username="alice", password="password123"):
    return client.post("/api/auth/login", json={
        "username": username, "password": password})


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def user_token(client):
    """Register 'alice' and return her JWT."""
    res = register(client, "alice")
    return res.get_json()["access_token"]


@pytest.fixture()
def second_user_token(client):
    """Register 'bob' and return his JWT."""
    res = register(client, "bob")
    return res.get_json()["access_token"]


@pytest.fixture()
def auth(user_token):
    return auth_headers(user_token)


@pytest.fixture()
def auth2(second_user_token):
    return auth_headers(second_user_token)
