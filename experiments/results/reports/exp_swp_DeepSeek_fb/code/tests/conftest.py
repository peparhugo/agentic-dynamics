import bcrypt
import pytest

from app import create_app
from app.extensions import db, limiter
from app.models import Item, User
from app.security import create_access_token


@pytest.fixture()
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path}/test.db",
            "JWT_SECRET_KEY": "test-secret-key-that-is-long-enough-for-hs256",
            "JWT_ACCESS_TOKEN_EXPIRES": 900,
            "JWT_REFRESH_TOKEN_EXPIRES": 604800,
            "RATELIMIT_ENABLED": True,
            "RATELIMIT_STORAGE_URI": "memory://",
            "LOGIN_RATE_LIMIT": "5 per minute",
        }
    )
    with application.app_context():
        db.create_all()
    limiter.reset()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()
    limiter.reset()


@pytest.fixture()
def client(app):
    return app.test_client()


def make_user(app, username="user1", email="user1@example.com", password="password123", role="user"):
    with app.app_context():
        pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        user = User(username=username, email=email, password_hash=pw, role=role)
        db.session.add(user)
        db.session.commit()
        return user.id


def auth_headers(app, user_id):
    with app.app_context():
        user = db.session.get(User, user_id)
        token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


def make_items(app, owner_id, count):
    with app.app_context():
        for i in range(count):
            db.session.add(Item(name=f"item-{i}", owner_id=owner_id))
        db.session.commit()


@pytest.fixture()
def user_id(app):
    return make_user(app)


@pytest.fixture()
def user_headers(app, user_id):
    return auth_headers(app, user_id)


@pytest.fixture()
def admin_id(app):
    return make_user(app, username="admin", email="admin@example.com", role="admin")


@pytest.fixture()
def admin_headers(app, admin_id):
    return auth_headers(app, admin_id)
