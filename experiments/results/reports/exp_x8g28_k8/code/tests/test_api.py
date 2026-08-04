import os
import sys
import pytest

# Ensure repository root is on sys.path so tests can import app.py
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app, USERS
import time


@pytest.fixture
def app():
    app = create_app({"TESTING": True, "SECRET_KEY": "test-secret"})
    yield app


@pytest.fixture
def client(app):
    with app.test_client() as c:
        # ensure storage clean for tests
        USERS.clear()
        yield c


def register(client, username="alice", password="s3cretp"):
    return client.post("/api/v1/register", json={"username": username, "password": password})


def login(client, username="alice", password="s3cretp"):
    return client.post("/api/v1/login", json={"username": username, "password": password})


def test_register_and_login(client):
    r = register(client)
    assert r.status_code == 201

    r = login(client)
    assert r.status_code == 200
    data = r.get_json()
    assert "access_token" in data


def test_register_validation(client):
    # Too short username/password should fail
    r = client.post("/api/v1/register", json={"username": "al", "password": "123"})
    assert r.status_code == 400


def test_protected_items_requires_token(client):
    r = client.get("/api/v1/items")
    assert r.status_code == 401


def test_items_pagination(client):
    register(client)
    token = login(client).get_json()["access_token"]
    # page 2 per_page 5
    r = client.get("/api/v1/items?page=2&per_page=5", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["pagination"]["page"] == 2
    assert len(data["items"]) == 5


def test_rate_limit_endpoint(client):
    # Uses test-only /api/v1/test-limit limited to 2 per minute
    r1 = client.get("/api/v1/test-limit")
    assert r1.status_code == 200
    r2 = client.get("/api/v1/test-limit")
    assert r2.status_code == 200
    r3 = client.get("/api/v1/test-limit")
    # rate limited
    assert r3.status_code in (429,)
