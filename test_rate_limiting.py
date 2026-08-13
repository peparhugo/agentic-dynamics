"""
Tests for API rate limiting (Flask-Limiter + Redis).

Each test builds its own app with a small, test-specific rate limit so
limits can be exceeded in a handful of requests instead of 100+.
"""

import pytest

from tasks_api import create_app

RATE_LIMIT_STORAGE_URI = "redis://localhost:6379/2"


@pytest.fixture
def app_factory(tmp_path):
    def _factory(rate_limit="3 per minute"):
        storage_path = tmp_path / "tasks.json"
        users_storage_path = tmp_path / "users.json"
        app = create_app(
            storage_path=str(storage_path),
            users_storage_path=str(users_storage_path),
            rate_limit_storage_uri=RATE_LIMIT_STORAGE_URI,
            rate_limit=rate_limit,
        )
        app.config["TESTING"] = True
        return app

    return _factory


def register_and_login(client, username="alice", password="password123"):
    client.post("/auth/register", json={"username": username, "password": password})
    resp = client.post("/auth/login", json={"username": username, "password": password})
    return resp.get_json()["token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ── Authenticated requests ───────────────────────────────────────

def test_requests_within_limit_all_succeed(app_factory):
    app = app_factory("5 per minute")
    client = app.test_client()
    headers = auth_headers(register_and_login(client))

    for _ in range(5):
        resp = client.get("/tasks", headers=headers)
        assert resp.status_code == 200


def test_authenticated_requests_beyond_limit_return_429(app_factory):
    app = app_factory("3 per minute")
    client = app.test_client()
    headers = auth_headers(register_and_login(client))

    for _ in range(3):
        assert client.get("/tasks", headers=headers).status_code == 200

    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 429
    assert "error" in resp.get_json()


def test_rate_limit_response_includes_retry_after_header(app_factory):
    app = app_factory("2 per minute")
    client = app.test_client()
    headers = auth_headers(register_and_login(client))

    client.get("/tasks", headers=headers)
    client.get("/tasks", headers=headers)
    resp = client.get("/tasks", headers=headers)

    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert int(resp.headers["Retry-After"]) >= 0


def test_rate_limit_shared_across_endpoints_for_same_user(app_factory):
    # The limit is a single per-user budget, not a separate quota per route.
    app = app_factory("3 per minute")
    client = app.test_client()
    headers = auth_headers(register_and_login(client))

    assert client.post("/tasks", json={"title": "a"}, headers=headers).status_code == 201
    assert client.get("/tasks", headers=headers).status_code == 200
    assert client.get("/tasks", headers=headers).status_code == 200

    resp = client.post("/tasks", json={"title": "b"}, headers=headers)
    assert resp.status_code == 429


def test_rate_limit_is_independent_per_user(app_factory):
    # Limit is high enough that the (IP-keyed) register/login setup calls
    # for both users never trip it; only the per-user buckets are exercised.
    app = app_factory("6 per minute")
    client = app.test_client()
    alice_headers = auth_headers(register_and_login(client, "alice", "password123"))
    bob_headers = auth_headers(register_and_login(client, "bob", "password123"))

    for _ in range(6):
        assert client.get("/tasks", headers=alice_headers).status_code == 200
    assert client.get("/tasks", headers=alice_headers).status_code == 429

    # Bob has his own, untouched quota.
    assert client.get("/tasks", headers=bob_headers).status_code == 200


# ── Unauthenticated (auth) endpoints ─────────────────────────────

def test_unauthenticated_requests_beyond_limit_return_429(app_factory):
    app = app_factory("3 per minute")
    client = app.test_client()

    for _ in range(3):
        resp = client.post("/auth/login", json={"username": "nobody", "password": "wrong"})
        assert resp.status_code == 401

    resp = client.post("/auth/login", json={"username": "nobody", "password": "wrong"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_register_endpoint_is_rate_limited(app_factory):
    app = app_factory("2 per minute")
    client = app.test_client()

    assert client.post("/auth/register", json={"username": "a", "password": "password123"}).status_code == 201
    assert client.post("/auth/register", json={"username": "b", "password": "password123"}).status_code == 201

    resp = client.post("/auth/register", json={"username": "c", "password": "password123"})
    assert resp.status_code == 429
