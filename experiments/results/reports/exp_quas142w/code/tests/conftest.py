import pytest
from werkzeug.security import generate_password_hash
from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models.user import User


@pytest.fixture(scope="function")
def app():
    app = create_app(config_class=TestConfig)
    app.config.update({"TESTING": True})
    return app


@pytest.fixture(scope="function")
def client(app):
    return app.test_client()


@pytest.fixture(scope="function")
def _db(app):
    with app.app_context():
        db.create_all()
        yield db
        db.drop_all()


@pytest.fixture(scope="function")
def admin_user(app, _db):
    with app.app_context():
        admin = User(
            username="admin",
            email="admin@example.com",
            password_hash=generate_password_hash("adminpass123"),
        )
        db.session.add(admin)
        db.session.commit()
        return admin


@pytest.fixture(scope="function")
def normal_user(app, _db):
    with app.app_context():
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash=generate_password_hash("testpass123"),
        )
        db.session.add(user)
        db.session.commit()
        return user


@pytest.fixture(scope="function")
def admin_token(client, admin_user):
    resp = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "adminpass123",
    })
    return resp.get_json()["access_token"]


@pytest.fixture(scope="function")
def user_token(client, normal_user):
    resp = client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "testpass123",
    })
    return resp.get_json()["access_token"]


@pytest.fixture(scope="function")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
