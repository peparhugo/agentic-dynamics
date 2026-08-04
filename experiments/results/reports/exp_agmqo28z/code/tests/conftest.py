import pytest
from app import create_app, db as _db
from app.models import User, AuditLog


@pytest.fixture
def app():
    app = create_app("config.TestConfig")
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def user(db, app):
    with app.app_context():
        from werkzeug.security import generate_password_hash
        u = User(
            username="testuser",
            email="test@example.com",
            password_hash=generate_password_hash("password123"),
        )
        db.session.add(u)
        db.session.commit()
        return u


@pytest.fixture
def auth_headers(client, user):
    resp = client.post(
        "/v1/auth/login",
        json={"username_or_email": "testuser", "password": "password123"},
    )
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def second_user(db, app):
    with app.app_context():
        from werkzeug.security import generate_password_hash
        u = User(
            username="otheruser",
            email="other@example.com",
            password_hash=generate_password_hash("password123"),
        )
        db.session.add(u)
        db.session.commit()
        return u
