import os
import json
import time
import pytest
import os
import sys

# Ensure repo root is on sys.path so tests can import the application package
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app

flask_app = create_app()
import app.auth as _auth_mod



@pytest.fixture
def client():
    flask_app.config.update({
        "TESTING": True,
        "JWT_SECRET": "test-secret",
        "RATE_LIMIT": 3,
        "RATE_PERIOD": 2,  # short for tests
    })
    with flask_app.test_client() as c:
        yield c


def login_and_get_token(client):
    r = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password123"})
    assert r.status_code == 200
    return r.get_json()["access_token"]


def test_login_bad_credentials(client):
    r = client.post("/api/v1/auth/login", json={"username": "bob", "password": "x"})
    assert r.status_code == 401


def test_protected_requires_token(client):
    r = client.get("/api/v1/items")
    assert r.status_code == 401


def test_list_items_pagination_and_auth(client):
    token = login_and_get_token(client)
    r = client.get("/api/v1/items?page=2&per_page=5", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["page"] == 2
    assert data["per_page"] == 5
    assert len(data["items"]) == 5


def test_input_validation(client):
    token = login_and_get_token(client)
    r = client.get("/api/v1/items?page=abc", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400


def test_rate_limiting(client):
    # reset any shared in-memory rate state to avoid interference between tests
    _auth_mod._rate_store.clear()
    token = login_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    # hit the limit
    for _ in range(3):
        r = client.get("/api/v1/items", headers=headers)
        assert r.status_code == 200
    r = client.get("/api/v1/items", headers=headers)
    assert r.status_code == 429
    # wait for window to pass
    time.sleep(2)
    r = client.get("/api/v1/items", headers=headers)
    assert r.status_code == 200
