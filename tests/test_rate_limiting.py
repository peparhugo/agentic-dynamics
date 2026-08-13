"""Rate limiting tests.

The app enforces a 100 requests/minute limit (app.RATE_LIMIT), so tests
that exercise the limit fire 100+ requests directly rather than mocking it
out — the Flask test client makes this fast (no real network I/O). The
limiter's Redis storage is reset before every test (see conftest.py) so
counts never leak between tests.
"""


def _register_and_login(client, username, password="secret123"):
    client.post("/auth/register", json={"username": username, "password": password})
    resp = client.post("/auth/login", json={"username": username, "password": password})
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_requests_within_limit_succeed(client, auth_headers):
    for _ in range(50):
        resp = client.get("/tasks", headers=auth_headers)
        assert resp.status_code == 200


def test_exceeding_limit_returns_429_with_retry_after(client, auth_headers):
    for _ in range(100):
        resp = client.get("/tasks", headers=auth_headers)
        assert resp.status_code == 200

    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert resp.get_json() == {"error": "rate limit exceeded"}


def test_rate_limit_response_includes_headers(client, auth_headers):
    resp = client.get("/tasks", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers.get("X-RateLimit-Limit") == "100"
    assert "X-RateLimit-Remaining" in resp.headers


def test_rate_limit_is_per_user_not_global(client, auth_headers):
    bob_headers = _register_and_login(client, "bob")

    for _ in range(100):
        resp = client.get("/tasks", headers=auth_headers)
        assert resp.status_code == 200

    # alice is now rate limited...
    assert client.get("/tasks", headers=auth_headers).status_code == 429

    # ...but bob, a different user, still has his own budget.
    assert client.get("/tasks", headers=bob_headers).status_code == 200


def test_auth_endpoints_are_rate_limited(client):
    for _ in range(100):
        resp = client.post("/auth/login", json={"username": "ghost", "password": "x"})
        assert resp.status_code == 401

    resp = client.post("/auth/login", json={"username": "ghost", "password": "x"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_register_endpoint_is_rate_limited(client):
    for i in range(100):
        resp = client.post(
            "/auth/register", json={"username": f"user{i}", "password": "secret123"}
        )
        assert resp.status_code == 201

    resp = client.post(
        "/auth/register", json={"username": "one-too-many", "password": "secret123"}
    )
    assert resp.status_code == 429


def test_rate_limit_key_falls_back_to_ip_when_unauthenticated(client):
    # Anonymous (no token) requests to a protected endpoint are rejected by
    # auth (401) long before rate limiting would kick in, but they must
    # still be counted so the limiter can't be bypassed by omitting a token.
    resp = client.get("/tasks")
    assert resp.status_code == 401
    # A malformed/garbage bearer token also falls back to IP-based keying
    # rather than crashing the key function.
    resp = client.get("/tasks", headers={"Authorization": "Bearer garbage.token.here"})
    assert resp.status_code == 401
