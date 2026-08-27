import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth(client):
    client.post(
        "/v1/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "password123"},
    )
    login = client.post("/v1/auth/login", json={"username": "alice", "password": "password123"})
    token = login.get_json()["access_token"]
    register_resp = client.get("/v1/users/1", headers={"Authorization": f"Bearer {token}"})
    user_id = register_resp.get_json()["id"]
    return {
        "token": token,
        "user_id": user_id,
        "headers": {"Authorization": f"Bearer {token}"},
    }
