import pytest

from app import create_app
from app.extensions import db, limiter
from app.models import User


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        limiter.reset()  # isolate rate-limit counters between tests
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def make_user(email="user@example.com", password="password123", role="user"):
    user = User(email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def user(app):
    return make_user()


@pytest.fixture()
def admin(app):
    return make_user(email="admin@example.com", role="admin")


def login(client, email="user@example.com", password="password123"):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


def auth_header(client, email="user@example.com", password="password123"):
    tokens = login(client, email, password)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture()
def auth(client, user):
    return auth_header(client)


@pytest.fixture()
def admin_auth(client, admin):
    return auth_header(client, email="admin@example.com")
