def test_login_rate_limited_after_5_attempts(client):
    client.post(
        "/v1/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "password123"},
    )
    for _ in range(5):
        resp = client.post(
            "/v1/auth/login", json={"username": "alice", "password": "wrong-password"}
        )
        assert resp.status_code == 401

    resp = client.post(
        "/v1/auth/login", json={"username": "alice", "password": "password123"}
    )
    assert resp.status_code == 429
    assert resp.get_json()["code"] == "rate_limited"
    assert "Retry-After" in resp.headers


def test_rate_limit_is_per_ip(client):
    client.post(
        "/v1/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "password123"},
    )
    for _ in range(5):
        client.post(
            "/v1/auth/login",
            json={"username": "alice", "password": "wrong-password"},
            headers={"X-Forwarded-For": "1.1.1.1"},
        )

    resp = client.post(
        "/v1/auth/login",
        json={"username": "alice", "password": "wrong-password"},
        headers={"X-Forwarded-For": "1.1.1.1"},
    )
    assert resp.status_code == 429

    resp = client.post(
        "/v1/auth/login",
        json={"username": "alice", "password": "wrong-password"},
        headers={"X-Forwarded-For": "2.2.2.2"},
    )
    assert resp.status_code == 401


def test_rate_limiter_reset(app):
    app.rate_limiter.hit("127.0.0.1")
    assert app.rate_limiter.is_limited("127.0.0.1") is False
    app.rate_limiter.reset()
    assert app.rate_limiter._hits == {}
