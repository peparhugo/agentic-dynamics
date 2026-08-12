"""
Tests for API rate limiting (Flask-Limiter, Redis storage backend).

Real Redis isn't available in the test environment; ``tests/conftest.py``
transparently swaps it for a fresh, isolated ``fakeredis`` instance per
test, so these tests exercise the exact same code path (Flask-Limiter ->
``limits`` Redis storage -> Lua-script atomic increments) that runs in
production.

Most tests use a small, explicit ``rate_limit`` override (via
``create_app``) so they run fast and deterministically; one test verifies
the actual production default of "100 per minute".
"""

import json

import pytest

from app import create_app


def make_app(tmp_path, rate_limit="3 per minute", **kwargs):
    flask_app = create_app(
        database=str(tmp_path / "test_tasks.db"),
        jwt_secret="test-secret",
        rate_limit=rate_limit,
        **kwargs,
    )
    flask_app.config.update(TESTING=True)
    return flask_app


def register(client, username="alice", password="s3cret-pw"):
    return client.post(
        "/auth/register",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


def login(client, username="alice", password="s3cret-pw"):
    return client.post(
        "/auth/login",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def create_task(client, token, title="Task"):
    return client.post(
        "/tasks",
        data=json.dumps({"title": title}),
        content_type="application/json",
        headers=auth_headers(token),
    )


# ── Basic breach behavior ────────────────────────────────────

def test_requests_within_limit_succeed(tmp_path):
    app = make_app(tmp_path, rate_limit="3 per minute")
    client = app.test_client()
    register(client, "alice", "s3cret-pw")
    token = login(client, "alice", "s3cret-pw").get_json()["token"]

    # Registration + login already consumed 2 of the 3 IP-scoped hits, but
    # task requests are scoped by *user*, a separate budget.
    for _ in range(3):
        resp = create_task(client, token)
        assert resp.status_code == 201


def test_exceeding_limit_returns_429(tmp_path):
    app = make_app(tmp_path, rate_limit="3 per minute")
    client = app.test_client()
    register(client, "alice", "s3cret-pw")
    token = login(client, "alice", "s3cret-pw").get_json()["token"]

    for _ in range(3):
        assert create_task(client, token).status_code == 201

    resp = create_task(client, token)
    assert resp.status_code == 429
    assert "error" in resp.get_json()


def test_429_response_has_retry_after_header(tmp_path):
    app = make_app(tmp_path, rate_limit="2 per minute")
    client = app.test_client()
    register(client, "alice", "s3cret-pw")
    token = login(client, "alice", "s3cret-pw").get_json()["token"]

    for _ in range(2):
        assert create_task(client, token).status_code == 201

    resp = create_task(client, token)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert int(resp.headers["Retry-After"]) >= 0


# ── Shared budget across endpoints ───────────────────────────

def test_limit_is_shared_across_endpoints_for_same_user(tmp_path):
    """Spreading calls across different routes doesn't dodge the limit."""
    app = make_app(tmp_path, rate_limit="2 per minute")
    client = app.test_client()
    register(client, "alice", "s3cret-pw")
    token = login(client, "alice", "s3cret-pw").get_json()["token"]

    # register+login spent hits from the IP-scoped budget, not the
    # user-scoped one. Spend the user-scoped budget across two different
    # endpoints.
    created = create_task(client, token, "First").get_json()  # user hit 1/2
    resp = client.get(f"/tasks/{created['id']}", headers=auth_headers(token))  # hit 2/2
    assert resp.status_code == 200

    # Budget for this user is now exhausted regardless of which endpoint
    # is hit next.
    resp = client.get("/tasks", headers=auth_headers(token))
    assert resp.status_code == 429


# ── Per-key isolation ─────────────────────────────────────────

def test_rate_limit_is_isolated_per_authenticated_user(tmp_path):
    app = make_app(tmp_path, rate_limit="2 per minute")
    client = app.test_client()

    # Register/login from distinct IPs so the (separately IP-scoped) setup
    # calls don't interfere with each other or with the user-scoped budget
    # under test below.
    client.post(
        "/auth/register",
        data=json.dumps({"username": "alice", "password": "pw-alice-1"}),
        content_type="application/json",
        environ_overrides={"REMOTE_ADDR": "10.0.0.1"},
    )
    token_alice = client.post(
        "/auth/login",
        data=json.dumps({"username": "alice", "password": "pw-alice-1"}),
        content_type="application/json",
        environ_overrides={"REMOTE_ADDR": "10.0.0.1"},
    ).get_json()["token"]

    client.post(
        "/auth/register",
        data=json.dumps({"username": "bob", "password": "pw-bob-1"}),
        content_type="application/json",
        environ_overrides={"REMOTE_ADDR": "10.0.0.2"},
    )
    token_bob = client.post(
        "/auth/login",
        data=json.dumps({"username": "bob", "password": "pw-bob-1"}),
        content_type="application/json",
        environ_overrides={"REMOTE_ADDR": "10.0.0.2"},
    ).get_json()["token"]

    # Exhaust alice's user-scoped budget.
    assert create_task(client, token_alice, "A1").status_code == 201
    assert create_task(client, token_alice, "A2").status_code == 201
    assert create_task(client, token_alice, "A3").status_code == 429

    # Bob is unaffected -- separate key (his own user id).
    assert create_task(client, token_bob, "B1").status_code == 201


# ── Auth endpoints are rate limited too ──────────────────────

def test_auth_endpoints_are_rate_limited(tmp_path):
    app = make_app(tmp_path, rate_limit="2 per minute")
    client = app.test_client()

    assert register(client, "alice", "s3cret-pw").status_code == 201  # hit 1/2
    assert login(client, "alice", "s3cret-pw").status_code == 200  # hit 2/2

    resp = login(client, "alice", "s3cret-pw")  # hit 3 -> breach
    assert resp.status_code == 429


def test_login_endpoint_returns_429_with_retry_after_when_exceeded(tmp_path):
    app = make_app(tmp_path, rate_limit="1 per minute")
    client = app.test_client()

    # First request (register) consumes the sole allowed hit for this IP.
    register(client, "alice", "s3cret-pw")

    resp = login(client, "alice", "s3cret-pw")
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


# ── Unauthenticated requests are limited by IP ───────────────

def test_unauthenticated_requests_are_limited_by_ip(tmp_path):
    app = make_app(tmp_path, rate_limit="1 per minute")
    client = app.test_client()

    resp1 = client.get("/tasks")  # no token -> 401, but still consumes a hit
    assert resp1.status_code == 401

    resp2 = client.get("/tasks")
    assert resp2.status_code == 429


# ── Production default ───────────────────────────────────────

def test_default_rate_limit_is_100_per_minute(tmp_path):
    app = create_app(
        database=str(tmp_path / "test_tasks.db"), jwt_secret="test-secret"
    )
    assert app.config["RATE_LIMIT"] == "100 per minute"

    app.config.update(TESTING=True)
    client = app.test_client()
    register(client, "alice", "s3cret-pw")
    token = login(client, "alice", "s3cret-pw").get_json()["token"]

    statuses = [create_task(client, token, f"T{i}").status_code for i in range(100)]
    assert all(status == 201 for status in statuses)

    resp = create_task(client, token, "One too many")
    assert resp.status_code == 429
