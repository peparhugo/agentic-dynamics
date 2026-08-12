"""
Tests for API rate limiting (Flask-Limiter, Redis storage backend).

Covers:
 - Each authenticated user gets their own 100 requests/minute budget,
   keyed by user id (not shared across users).
 - Exceeding the limit returns 429 with a JSON error body and a
   Retry-After header.
 - Rate limiting also applies to unauthenticated endpoints (/auth/register,
   /auth/login), keyed by client IP since there's no user yet.
 - A rate-limited user doesn't affect another user's budget.
 - Once a user is under the limit again (simulated via limiter.reset()),
   requests succeed again.
"""

import json

import pytest

import app as app_module

RATE_LIMIT = 100  # requests per minute, per identity (see app.RATE_LIMIT)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test_rate_limiting.db"
    monkeypatch.setattr(app_module, "DATABASE", str(db_path))
    app_module.init_db()

    # Start every test with a clean rate-limit budget; these tests
    # deliberately exhaust limits so isolation from other tests/files
    # (which share the same Redis-backed storage) is essential.
    app_module.limiter.reset()

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client
        # Leave the shared storage clean for whatever runs next.
        app_module.limiter.reset()


def _register(client, username="alice", password="s3cret-pw"):
    return client.post(
        "/auth/register",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


def _login(client, username="alice", password="s3cret-pw"):
    return client.post(
        "/auth/login",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


def _register_and_login(client, username="alice", password="s3cret-pw"):
    _register(client, username, password)
    token = _login(client, username, password).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ── Basic behavior under the limit ──────────────────────────────────


def test_requests_under_limit_succeed(client):
    headers = _register_and_login(client)
    for _ in range(10):
        resp = client.get("/tasks", headers=headers)
        assert resp.status_code == 200


def test_rate_limit_headers_present(client):
    headers = _register_and_login(client)
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers


# ── Exceeding the limit ──────────────────────────────────────────────


def test_exceeding_limit_returns_429_with_retry_after(client):
    headers = _register_and_login(client)

    last_resp = None
    for _ in range(RATE_LIMIT + 1):
        last_resp = client.get("/tasks", headers=headers)

    assert last_resp.status_code == 429
    assert "Retry-After" in last_resp.headers
    assert int(last_resp.headers["Retry-After"]) >= 0
    body = last_resp.get_json()
    assert "error" in body


def test_requests_before_limit_reached_still_succeed(client):
    headers = _register_and_login(client)

    responses = [client.get("/tasks", headers=headers) for _ in range(RATE_LIMIT)]
    assert all(r.status_code == 200 for r in responses)

    # The 101st request in the same window is rejected.
    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 429


def test_rate_limit_applies_per_endpoint_hits_combined(client):
    """The budget is shared across all endpoints hit by the same user, not
    a separate 100/min per-route allowance."""
    headers = _register_and_login(client)

    task = client.post(
        "/tasks",
        data=json.dumps({"title": "x"}),
        content_type="application/json",
        headers=headers,
    ).get_json()

    responses = []
    for i in range(RATE_LIMIT):
        if i % 2 == 0:
            responses.append(client.get("/tasks", headers=headers))
        else:
            responses.append(client.get(f"/tasks/{task['id']}", headers=headers))

    assert responses[-1].status_code == 429


# ── Per-user isolation ────────────────────────────────────────────────


def test_rate_limit_is_isolated_per_user(client):
    alice_headers = _register_and_login(client, "alice", "pw-alice")
    bob_headers = _register_and_login(client, "bob", "pw-bob")

    # Exhaust alice's budget.
    for _ in range(RATE_LIMIT + 1):
        alice_resp = client.get("/tasks", headers=alice_headers)
    assert alice_resp.status_code == 429

    # Bob is unaffected — he has his own budget.
    bob_resp = client.get("/tasks", headers=bob_headers)
    assert bob_resp.status_code == 200


# ── Auth endpoints are rate limited too ───────────────────────────────


def test_login_endpoint_is_rate_limited(client):
    _register(client, "alice", "s3cret-pw")

    last_resp = None
    for _ in range(RATE_LIMIT + 1):
        last_resp = _login(client, "alice", "s3cret-pw")

    assert last_resp.status_code == 429
    assert "Retry-After" in last_resp.headers


def test_register_endpoint_is_rate_limited(client):
    last_resp = None
    for i in range(RATE_LIMIT + 1):
        last_resp = _register(client, f"user{i}", "s3cret-pw")

    assert last_resp.status_code == 429
    assert "Retry-After" in last_resp.headers


# ── Recovery ──────────────────────────────────────────────────────────


def test_limit_recovers_after_reset(client):
    headers = _register_and_login(client)

    for _ in range(RATE_LIMIT + 1):
        resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 429

    # Simulates the window rolling over.
    app_module.limiter.reset()

    resp = client.get("/tasks", headers=headers)
    assert resp.status_code == 200
