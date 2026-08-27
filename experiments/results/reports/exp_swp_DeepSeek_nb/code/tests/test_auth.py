def test_register_success(client):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "bob", "email": "bob@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "bob"
    assert data["email"] == "bob@example.com"
    assert "password_hash" not in data
    assert "password" not in data


def test_register_duplicate_username(client, user):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "alice", "email": "other@example.com", "password": "password123"},
    )
    assert resp.status_code == 409


def test_register_duplicate_email(client, user):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "other", "email": "alice@example.com", "password": "password123"},
    )
    assert resp.status_code == 409


def test_register_invalid_username(client):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "ab", "email": "x@example.com", "password": "password123"},
    )
    assert resp.status_code == 422


def test_register_invalid_email(client):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "validname", "email": "not-an-email", "password": "password123"},
    )
    assert resp.status_code == 422


def test_register_short_password(client):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "validname", "email": "x@example.com", "password": "short"},
    )
    assert resp.status_code == 422


def test_register_missing_fields(client):
    resp = client.post("/v1/auth/register", json={"username": "onlyuser"})
    assert resp.status_code == 422


def test_register_non_json(client):
    resp = client.post("/v1/auth/register", data="not json", content_type="text/plain")
    assert resp.status_code == 422


def test_login_success(client, user):
    resp = client.post(
        "/v1/auth/login", json={"username": "alice", "password": "password123"}
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["token_type"] == "Bearer"
    assert data["expires_in"] > 0


def test_login_wrong_password(client, user):
    resp = client.post(
        "/v1/auth/login", json={"username": "alice", "password": "wrongpassword"}
    )
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post(
        "/v1/auth/login", json={"username": "ghost", "password": "password123"}
    )
    assert resp.status_code == 401


def test_login_missing_credentials(client):
    resp = client.post("/v1/auth/login", json={})
    assert resp.status_code == 401


def test_refresh_success(client, tokens):
    resp = client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["refresh_token"] != tokens["refresh_token"]


def test_refresh_token_is_rotated(client, tokens):
    first = client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first.status_code == 200
    new_token = first.get_json()["refresh_token"]

    # Old token should now be revoked.
    again = client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert again.status_code == 401

    # New token should still work.
    ok = client.post("/v1/auth/refresh", json={"refresh_token": new_token})
    assert ok.status_code == 200


def test_refresh_invalid_token(client):
    resp = client.post("/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert resp.status_code == 401


def test_refresh_missing_token(client):
    resp = client.post("/v1/auth/refresh", json={})
    assert resp.status_code == 401


def test_logout_revokes_refresh_token(client, tokens):
    resp = client.post(
        "/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200

    after = client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert after.status_code == 401
