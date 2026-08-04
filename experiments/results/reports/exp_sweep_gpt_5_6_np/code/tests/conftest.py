import pytest

from app import create_app
from app.extensions import db


@pytest.fixture()
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
            "JWT_SECRET_KEY": "test-secret",
        }
    )
    with application.app_context():
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def registered(client):
    response = client.post(
        "/v1/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    )
    return response.get_json()


@pytest.fixture()
def auth_headers(registered):
    return {"Authorization": f"Bearer {registered['access_token']}"}
