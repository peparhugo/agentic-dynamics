def test_register_success(client):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "newuser", "email": "new@example.com", "password": "secure123"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["username"] == "newuser"
    assert data["email"] == "new@example.com"
    assert "password_hash" not in data
    assert "id" in data


def test_register_duplicate_username(client):
    client.post(
        "/v1/auth/register",
        json={"username": "dupuser", "email": "dup1@example.com", "password": "secure123"},
    )
    resp = client.post(
        "/v1/auth/register",
        json={"username": "dupuser", "email": "dup2@example.com", "password": "secure123"},
    )
    assert resp.status_code == 409
    data = resp.get_json()
    assert "already taken" in data["error"]


def test_register_duplicate_email(client):
    client.post(
        "/v1/auth/register",
        json={"username": "user1", "email": "same@example.com", "password": "secure123"},
    )
    resp = client.post(
        "/v1/auth/register",
        json={"username": "user2", "email": "same@example.com", "password": "secure123"},
    )
    assert resp.status_code == 409
    data = resp.get_json()
    assert "already registered" in data["error"]


def test_register_invalid_email(client):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "newuser", "email": "notanemail", "password": "secure123"},
    )
    assert resp.status_code == 422


def test_register_short_password(client):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "newuser", "email": "new@example.com", "password": "12345"},
    )
    assert resp.status_code == 422


def test_register_short_username(client):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "ab", "email": "new@example.com", "password": "secure123"},
    )
    assert resp.status_code == 422


def test_register_missing_fields(client):
    resp = client.post("/v1/auth/register", json={"username": "test"})
    assert resp.status_code == 422


def test_register_invalid_username_chars(client):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "bad-user", "email": "new@example.com", "password": "secure123"},
    )
    assert resp.status_code == 422


def test_login_success(client):
    client.post(
        "/v1/auth/register",
        json={"username": "logintest", "email": "login@example.com", "password": "secure123"},
    )
    resp = client.post(
        "/v1/auth/login",
        json={"username": "logintest", "password": "secure123"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_invalid_credentials(client):
    resp = client.post(
        "/v1/auth/login",
        json={"username": "nobody", "password": "wrong"},
    )
    assert resp.status_code == 401
    data = resp.get_json()
    assert "Invalid" in data["error"]


def test_login_invalid_password(client):
    client.post(
        "/v1/auth/register",
        json={"username": "pwtest", "email": "pw@example.com", "password": "secure123"},
    )
    resp = client.post(
        "/v1/auth/login",
        json={"username": "pwtest", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


def test_login_missing_fields(client):
    resp = client.post("/v1/auth/login", json={})
    assert resp.status_code == 422


def test_refresh_success(client, refresh_token):
    resp = client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data


def test_refresh_invalid_token(client):
    resp = client.post("/v1/auth/refresh", json={"refresh_token": "bad-token"})
    assert resp.status_code == 401


def test_refresh_missing_token(client):
    resp = client.post("/v1/auth/refresh", json={})
    assert resp.status_code == 422


def test_me_success(client, auth_headers):
    resp = client.get("/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"


def test_me_no_token(client):
    resp = client.get("/v1/auth/me")
    assert resp.status_code == 401


def test_me_bad_token(client):
    resp = client.get("/v1/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code == 401


def test_me_missing_bearer(client):
    resp = client.get("/v1/auth/me", headers={"Authorization": "Token something"})
    assert resp.status_code == 401


def test_register_empty_username(client):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "", "email": "test@example.com", "password": "secure123"},
    )
    assert resp.status_code == 422


def test_register_empty_password(client):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "newuser", "email": "test@example.com", "password": ""},
    )
    assert resp.status_code == 422
