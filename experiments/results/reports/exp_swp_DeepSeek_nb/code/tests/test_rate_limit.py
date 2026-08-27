def test_login_rate_limited(client, user):
    for _ in range(5):
        resp = client.post(
            "/v1/auth/login", json={"username": "alice", "password": "wrongpassword"}
        )
        assert resp.status_code == 401

    # 6th attempt (even with correct password) should be blocked.
    resp = client.post(
        "/v1/auth/login", json={"username": "alice", "password": "password123"}
    )
    assert resp.status_code == 429
    data = resp.get_json()
    assert data["error"] == "rate_limit_exceeded"
    assert "retry_after" in data.get("details", {})


def test_successful_login_also_counts_toward_limit(client, user):
    for _ in range(5):
        client.post("/v1/auth/login", json={"username": "alice", "password": "password123"})

    resp = client.post(
        "/v1/auth/login", json={"username": "alice", "password": "password123"}
    )
    assert resp.status_code == 429


def test_rate_limit_is_per_ip(app, client, user):
    app.extensions["rate_limiter"].reset()

    # Use a distinct IP via environ override.
    for _ in range(5):
        client.post(
            "/v1/auth/login",
            json={"username": "alice", "password": "wrongpassword"},
            environ_overrides={"REMOTE_ADDR": "1.2.3.4"},
        )

    # A different IP is unaffected.
    other_ip = client.post(
        "/v1/auth/login",
        json={"username": "alice", "password": "password123"},
        environ_overrides={"REMOTE_ADDR": "5.6.7.8"},
    )
    assert other_ip.status_code == 200

    # Same IP is blocked.
    blocked = client.post(
        "/v1/auth/login",
        json={"username": "alice", "password": "password123"},
        environ_overrides={"REMOTE_ADDR": "1.2.3.4"},
    )
    assert blocked.status_code == 429
