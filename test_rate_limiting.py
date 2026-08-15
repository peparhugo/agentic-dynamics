import os
import tempfile

import pytest
import redis

import app as app_module


@pytest.fixture()
def client():
    db_fd, db_path = tempfile.mkstemp()
    app_module.DATABASE = db_path
    app_module.app.config["TESTING"] = True
    app_module.limiter.enabled = True
    # Flush the rate-limit storage db so counts from a previous test run
    # don't bleed into this one (the limiter's Redis instance is shared and
    # persists across tests).
    redis.Redis.from_url(app_module.RATELIMIT_STORAGE_URI).flushdb()
    app_module.init_db()
    with app_module.app.test_client() as client:
        yield client
    app_module.limiter.enabled = False
    redis.Redis.from_url(app_module.RATELIMIT_STORAGE_URI).flushdb()
    os.close(db_fd)
    os.unlink(db_path)


def register(client, username="alice", password="password123"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="password123"):
    return client.post("/auth/login", json={"username": username, "password": password})


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ── Within limit ─────────────────────────────────────────────────

def test_requests_within_limit_succeed(client):
    register(client)
    token = login(client).get_json()["token"]
    for _ in range(5):
        resp = client.get("/tasks", headers=auth_header(token))
        assert resp.status_code == 200


# ── Exceeding the limit ─────────────────────────────────────────

def test_exceeding_limit_returns_429_with_retry_after(client):
    register(client)
    token = login(client).get_json()["token"]

    responses = [client.get("/tasks", headers=auth_header(token)) for _ in range(101)]

    assert [r.status_code for r in responses[:100]] == [200] * 100
    assert responses[100].status_code == 429
    assert "Retry-After" in responses[100].headers
    assert responses[100].headers["Retry-After"].isdigit()


def test_rate_limit_error_body_is_json(client):
    register(client)
    token = login(client).get_json()["token"]

    for _ in range(100):
        client.get("/tasks", headers=auth_header(token))
    resp = client.get("/tasks", headers=auth_header(token))

    assert resp.status_code == 429
    assert resp.get_json() == {"error": "rate limit exceeded"}


# ── Applies to auth endpoints too ───────────────────────────────

def test_rate_limit_applies_to_register_endpoint(client):
    responses = [
        client.post(
            "/auth/register",
            json={"username": f"user{i}", "password": "password123"},
        )
        for i in range(101)
    ]
    assert responses[100].status_code == 429


def test_rate_limit_applies_to_login_endpoint(client):
    register(client)
    responses = [login(client) for _ in range(101)]
    assert responses[100].status_code == 429


# ── Limits are keyed per user / IP ───────────────────────────────

def test_different_authenticated_users_have_independent_limits(client):
    register(client, username="alice")
    register(client, username="bob")
    alice_token = login(client, username="alice").get_json()["token"]
    bob_token = login(client, username="bob").get_json()["token"]

    for _ in range(100):
        resp = client.get("/tasks", headers=auth_header(alice_token))
        assert resp.status_code == 200

    assert client.get("/tasks", headers=auth_header(alice_token)).status_code == 429
    assert client.get("/tasks", headers=auth_header(bob_token)).status_code == 200
