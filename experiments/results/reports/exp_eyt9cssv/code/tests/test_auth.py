def test_register_success(client):
    resp = client.post(
        "/v1/auth/register",
        json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "password123",
        },
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["username"] == "newuser"


def test_register_duplicate_email(client):
    client.post(
        "/v1/auth/register",
        json={"username": "u1", "email": "dup@example.com", "password": "password123"},
    )
    resp = client.post(
        "/v1/auth/register",
        json={"username": "u2", "email": "dup@example.com", "password": "password123"},
    )
    assert resp.status_code == 409


def test_register_duplicate_username(client):
    client.post(
        "/v1/auth/register",
        json={"username": "same", "email": "a@example.com", "password": "password123"},
    )
    resp = client.post(
        "/v1/auth/register",
        json={"username": "same", "email": "b@example.com", "password": "password123"},
    )
    assert resp.status_code == 409


def test_register_validation(client):
    resp = client.post(
        "/v1/auth/register",
        json={"username": "ab", "email": "bad", "password": "short"},
    )
    assert resp.status_code == 422
    data = resp.get_json()
    assert data["error"] == "validation_error"


def test_login_success(client):
    client.post(
        "/v1/auth/register",
        json={"username": "loginuser", "email": "login@example.com", "password": "password123"},
    )
    resp = client.post(
        "/v1/auth/login",
        json={"email": "login@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_invalid_credentials(client):
    resp = client.post(
        "/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "wrongpass"},
    )
    assert resp.status_code == 401


def test_login_validation(client):
    resp = client.post("/v1/auth/login", json={"email": "notanemail"})
    assert resp.status_code == 422


def test_refresh_token_success(client):
    client.post(
        "/v1/auth/register",
        json={"username": "refreshu", "email": "refresh@example.com", "password": "password123"},
    )
    login_resp = client.post(
        "/v1/auth/login",
        json={"email": "refresh@example.com", "password": "password123"},
    )
    refresh_token = login_resp.get_json()["refresh_token"]

    resp = client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_refresh_invalid_token(client):
    resp = client.post("/v1/auth/refresh", json={"refresh_token": "invalid.token.here"})
    assert resp.status_code == 401


def test_access_protected_route_without_token(client):
    resp = client.get("/v1/items")
    assert resp.status_code == 401


def test_access_protected_route_with_invalid_token(client):
    resp = client.get("/v1/items", headers={"Authorization": "Bearer invalid.token"})
    assert resp.status_code == 401


def test_access_protected_with_refresh_token(client):
    client.post(
        "/v1/auth/register",
        json={"username": "tokentest", "email": "token@example.com", "password": "password123"},
    )
    login_resp = client.post(
        "/v1/auth/login",
        json={"email": "token@example.com", "password": "password123"},
    )
    refresh_token = login_resp.get_json()["refresh_token"]

    resp = client.get("/v1/items", headers={"Authorization": f"Bearer {refresh_token}"})
    assert resp.status_code == 401
