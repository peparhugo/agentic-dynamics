import pytest
from app import create_app, db as _db
from app.config import TestConfig
from app.models import User


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    with app.app_context():
        yield _db


@pytest.fixture
def _seed_user(app):
    with app.app_context():
        user = User(name="Test User", email="test@example.com", role="user")
        user.set_password("password123")
        _db.session.add(user)
        admin = User(name="Admin", email="admin@example.com", role="admin")
        admin.set_password("adminpass123")
        _db.session.add(admin)
        _db.session.commit()
        return {"user": user, "admin": admin}


@pytest.fixture
def auth_header(client):
    client.post("/api/v1/auth/register", json={
        "name": "Auth", "email": "authtest@example.com", "password": "password123"
    })
    resp = client.post("/api/v1/auth/login", json={
        "email": "authtest@example.com", "password": "password123"
    })
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_header(client):
    client.post("/api/v1/auth/register", json={
        "name": "Adm", "email": f"admauth@example.com", "password": "adminpass123"
    })
    from app import db
    with client.application.app_context():
        u = db.session.get(User, 1) or User.query.filter_by(email="admauth@example.com").first()
        if u:
            u.role = "admin"
            db.session.commit()
    resp = client.post("/api/v1/auth/login", json={
        "email": "admauth@example.com", "password": "adminpass123"
    })
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}
