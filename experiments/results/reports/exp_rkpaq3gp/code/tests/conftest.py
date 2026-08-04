import pytest
from app import create_app, db as _db
from app.config import TestConfig
from app.models.user import User
from app.models.item import Item


@pytest.fixture(scope="session")
def app():
    _app = create_app(TestConfig)
    return _app


@pytest.fixture(scope="function")
def client(app):
    with app.test_client() as client:
        with app.app_context():
            _db.create_all()
        yield client
        with app.app_context():
            _db.drop_all()


@pytest.fixture(scope="function")
def db(app):
    with app.app_context():
        _db.create_all()
    yield _db
    with app.app_context():
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope="function")
def _db_session(db):
    return db.session


@pytest.fixture
def auth_headers(client):
    client.post("/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123",
    })
    resp = client.post("/auth/login", json={
        "username": "testuser",
        "password": "testpass123",
    })
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def registered_user():
    return {"username": "bob", "email": "bob@example.com", "password": "password123"}
