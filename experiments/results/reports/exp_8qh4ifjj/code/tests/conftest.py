import pytest

from app import create_app
from app.config import TestConfig
from app.db import get_db


@pytest.fixture()
def app(tmp_path):
    app = create_app(TestConfig, DATABASE=str(tmp_path / "test.db"), TESTING=True)
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_headers(client):
    def _headers(token):
        return {"Authorization": f"Bearer {token}"}

    return _headers


@pytest.fixture()
def user_a(client):
    res = client.post("/api/auth/register", json={"username": "alice", "password": "secret123"})
    assert res.status_code == 201
    return res.get_json()


@pytest.fixture()
def user_b(client):
    res = client.post("/api/auth/register", json={"username": "bob", "password": "secret123"})
    assert res.status_code == 201
    return res.get_json()


@pytest.fixture()
def auth_a(user_a):
    return {"Authorization": f"Bearer {user_a['token']}"}


@pytest.fixture()
def auth_b(user_b):
    return {"Authorization": f"Bearer {user_b['token']}"}
