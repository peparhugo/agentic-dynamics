from app.extensions import limiter

from tests.conftest import make_user


def test_login_rate_limited(app, client):
    limiter.reset()
    make_user(app, username="ratelimit", email="ratelimit@example.com")

    for i in range(5):
        resp = client.post(
            "/v1/auth/login", json={"username": "ratelimit", "password": "password123"}
        )
        assert resp.status_code == 200, f"attempt {i} unexpected {resp.status_code}"

    resp = client.post(
        "/v1/auth/login", json={"username": "ratelimit", "password": "password123"}
    )
    assert resp.status_code == 429


def test_rate_limit_headers_present(app, client):
    limiter.reset()
    make_user(app, username="ratelimit2", email="ratelimit2@example.com")
    resp = client.post(
        "/v1/auth/login", json={"username": "ratelimit2", "password": "password123"}
    )
    assert resp.status_code == 200
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
