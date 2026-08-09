import re


def test_register_success(client):
    resp = client.post(
        "/v1/auth/register",
        json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "securepass123",
        },
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["username"] == "newuser"
    assert data["user"]["email"] == "new@example.com"
    assert "password_hash" not in data["user"]


def test_register_missing_fields(client):
    resp = client.post("/v1/auth/register", json={})
    assert resp.status_code == 422
    assert "missing" in resp.get_json()["message"].lower()


def test_register_duplicate_username(client, user):
    resp = client.post(
        "/v1/auth/register",
        json={
            "username": "testuser",
            "email": "unique@example.com",
            "password": "securepass123",
        },
    )
    assert resp.status_code == 409


def test_register_duplicate_email(client, user):
    resp = client.post(
        "/v1/auth/register",
        json={
            "username": "uniquename",
            "email": "test@example.com",
            "password": "securepass123",
        },
    )
    assert resp.status_code == 409


def test_register_invalid_username(client):
    resp = client.post(
        "/v1/auth/register",
        json={
            "username": "ab",
            "email": "test@example.com",
            "password": "securepass123",
        },
    )
    assert resp.status_code == 422


def test_register_invalid_email(client):
    resp = client.post(
        "/v1/auth/register",
        json={
            "username": "validuser",
            "email": "not-an-email",
            "password": "securepass123",
        },
    )
    assert resp.status_code == 422


def test_register_short_password(client):
    resp = client.post(
        "/v1/auth/register",
        json={
            "username": "validuser",
            "email": "valid@example.com",
            "password": "short",
        },
    )
    assert resp.status_code == 422


def test_register_bad_json(client):
    resp = client.post(
        "/v1/auth/register",
        data="not json",
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_login_success(client, user):
    resp = client.post(
        "/v1/auth/login",
        json={"username_or_email": "testuser", "password": "password123"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_with_email(client, user):
    resp = client.post(
        "/v1/auth/login",
        json={"username_or_email": "test@example.com", "password": "password123"},
    )
    assert resp.status_code == 200


def test_login_invalid_password(client, user):
    resp = client.post(
        "/v1/auth/login",
        json={"username_or_email": "testuser", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


def test_login_nonexistent_user(client):
    resp = client.post(
        "/v1/auth/login",
        json={
            "username_or_email": "nonexistent",
            "password": "password123",
        },
    )
    assert resp.status_code == 401


def test_login_missing_fields(client):
    resp = client.post("/v1/auth/login", json={})
    assert resp.status_code == 422


def test_login_bad_json(client):
    resp = client.post(
        "/v1/auth/login",
        data="bad",
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_refresh_token_success(client, user):
    login_resp = client.post(
        "/v1/auth/login",
        json={"username_or_email": "testuser", "password": "password123"},
    )
    refresh_token = login_resp.get_json()["refresh_token"]

    resp = client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_refresh_token_invalid(client):
    resp = client.post("/v1/auth/refresh", json={"refresh_token": "invalid"})
    assert resp.status_code == 401


def test_refresh_token_missing(client):
    resp = client.post("/v1/auth/refresh", json={})
    assert resp.status_code == 400


def test_refresh_with_access_token(client, user):
    login_resp = client.post(
        "/v1/auth/login",
        json={"username_or_email": "testuser", "password": "password123"},
    )
    access_token = login_resp.get_json()["access_token"]

    resp = client.post("/v1/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401


def test_login_rate_limit(client, user):
    # Hit rate limit: 5 attempts in 60 seconds
    responses = []
    for _ in range(5):
        resp = client.post(
            "/v1/auth/login",
            json={"username_or_email": "testuser", "password": "password123"},
        )
        responses.append(resp.status_code)

    # 6th should be rate limited
    resp = client.post(
        "/v1/auth/login",
        json={"username_or_email": "testuser", "password": "password123"},
    )
    assert resp.status_code == 429

    # Earlier 5 should all have succeeded (valid credentials)
    assert all(s == 200 for s in responses)
