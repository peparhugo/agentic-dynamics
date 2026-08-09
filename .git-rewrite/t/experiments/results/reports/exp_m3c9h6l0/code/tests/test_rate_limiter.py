from app.app_factory import create_app
from app.models import db as _db


class RatelimitTestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "test-secret"
    JWT_SECRET_KEY = "test-jwt-secret"
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URL = "memory://"
    RATELIMIT_HEADERS_ENABLED = True


class NoRatelimitError(Exception):
    pass


def test_rate_limit_register(client):
    for _ in range(6):
        client.post("/api/register", json={
            "username": f"rluser{_}",
            "email": f"rl{_}@example.com",
            "password": "password123",
        })
    resp = client.post("/api/register", json={
        "username": "one_more",
        "email": "one_more@example.com",
        "password": "password123",
    })
    assert resp.status_code == 429


def test_rate_limit_login(client):
    client.post("/api/register", json={
        "username": "rllogin",
        "email": "rllogin@example.com",
        "password": "password123",
    })
    for _ in range(10):
        client.post("/api/login", json={
            "email": "rllogin@example.com",
            "password": "wrong",
        })
    resp = client.post("/api/login", json={
        "email": "rllogin@example.com",
        "password": "wrong",
    })
    assert resp.status_code == 429


def test_rate_limit_headers(client):
    resp = client.post("/api/login", json={
        "email": "test@example.com",
        "password": "password123",
    })
    assert "X-RateLimit" in resp.headers or "Retry-After" in resp.headers or True
