import pytest
from app import create_app
from config import TestConfig
from models import db as _db


@pytest.fixture(scope="session")
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture(autouse=True)
def clean_db(app):
    """Reset database tables between tests for isolation."""
    with app.app_context():
        meta = _db.metadata
        for table in reversed(meta.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_header(client):
    """Register a test user and return the Authorization header dict."""
    resp = client.post(
        "/api/auth/register",
        json={"username": "testuser", "email": "test@example.com", "password": "secret123"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    return {"Authorization": f"Bearer {data['access_token']}"}


@pytest.fixture
def auth_header2(client):
    """Register a second test user."""
    resp = client.post(
        "/api/auth/register",
        json={"username": "otheruser", "email": "other@example.com", "password": "secret123"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]
