from tests.conftest import register_user


def _login_attempt(client, email="user@example.com", password="password123"):
    return client.post("/v1/auth/login", json={"email": email, "password": password})


def test_login_rate_limited_after_5_attempts(client, app):
    register_user(client)

    statuses = []
    for _ in range(5):
        resp = _login_attempt(client)
        statuses.append(resp.status_code)

    assert statuses == [200] * 5

    resp = _login_attempt(client)
    assert resp.status_code == 429
    body = resp.get_json()
    assert body["error"] == "rate_limited"
    assert resp.headers.get("Retry-After") is not None


def test_rate_limit_is_per_ip(client, app):
    register_user(client, email="user@example.com")

    for _ in range(5):
        assert _login_attempt(client).status_code == 200

    # A different IP should not be blocked.
    assert _login_attempt(
        client, email="user@example.com"
    ).status_code == 429

    # Simulate a different client IP.
    other = app.test_client()
    other.environ_base["REMOTE_ADDR"] = "10.0.0.99"
    resp = other.post(
        "/v1/auth/login", json={"email": "user@example.com", "password": "password123"}
    )
    assert resp.status_code == 200


def test_rate_limit_reset(client, app):
    register_user(client)
    for _ in range(5):
        _login_attempt(client)
    assert _login_attempt(client).status_code == 429

    app.login_limiter.reset()
    assert _login_attempt(client).status_code == 200
