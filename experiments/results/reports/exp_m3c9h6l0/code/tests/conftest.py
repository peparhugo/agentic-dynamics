import pytest
from app import create_app
from app.models import db as _db


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "test-secret"
    JWT_SECRET_KEY = "test-jwt-secret"
    RATELIMIT_ENABLED = False
    RATELIMIT_STORAGE_URL = "memory://"
    RATELIMIT_HEADERS_ENABLED = True


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def auth_headers(client):
    client.post("/api/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123",
    })
    resp = client.post("/api/login", json={
        "email": "test@example.com",
        "password": "password123",
    })
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_id(auth_headers):
    return auth_headers


@pytest.fixture
def sample_item(client, auth_headers):
    resp = client.post("/api/v1/items", json={
        "name": "Test Item",
        "description": "A sample item",
        "price": 9.99,
        "category": "Electronics",
    }, headers=auth_headers)
    return resp.get_json()["data"]
