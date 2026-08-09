import pytest
from app.factory import create_app
from app.config import TestConfig
from app.extensions import db as _db
from app.models.user import User
from app.models.item import Item
from app.models.audit_log import AuditLog


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.rollback()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    with app.app_context():
        yield _db


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


def _make_user(username="testuser", email="test@example.com", password="password123", role="user", active=True):
    user = User(username=username, email=email, role=role, is_active=active)
    user.set_password(password)
    return user


def _get_token(client, username="testuser", password="password123"):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    data = resp.get_json()
    return data.get("access_token") if data else None


@pytest.fixture
def auth_user(db):
    user = _make_user()
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def auth_token(client, auth_user):
    return _get_token(client)


@pytest.fixture
def auth_headers(client, auth_user):
    token = _get_token(client)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_user(db):
    user = _make_user(username="admin", email="admin@example.com", password="adminpass", role="admin")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def admin_headers(client, admin_user):
    token = _get_token(client, username="admin", password="adminpass")
    return {"Authorization": f"Bearer {token}"}
