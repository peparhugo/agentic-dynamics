def test_register_success(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"username": "newuser", "email": "new@example.com", "password": "secret123"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["message"] == "User registered successfully"
    assert data["user"]["username"] == "newuser"


def test_register_duplicate_username(client, auth_user):
    resp = client.post(
        "/api/v1/auth/register",
        json={"username": "testuser", "email": "other@example.com", "password": "secret123"},
    )
    assert resp.status_code == 409
    assert "already taken" in resp.get_json()["error"]


def test_register_duplicate_email(client, auth_user):
    resp = client.post(
        "/api/v1/auth/register",
        json={"username": "other", "email": "test@example.com", "password": "secret123"},
    )
    assert resp.status_code == 409
    assert "already registered" in resp.get_json()["error"]


def test_register_missing_fields(client):
    resp = client.post("/api/v1/auth/register", json={"username": "x"})
    assert resp.status_code == 422
    assert "Validation failed" in resp.get_json()["error"]


def test_register_short_password(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"username": "newuser", "email": "new@example.com", "password": "ab"},
    )
    assert resp.status_code == 422


def test_login_success(client, auth_user):
    resp = client.post("/api/v1/auth/login", json={"username": "testuser", "password": "password123"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert data["token_type"] == "Bearer"


def test_login_wrong_password(client, auth_user):
    resp = client.post("/api/v1/auth/login", json={"username": "testuser", "password": "wrongpass"})
    assert resp.status_code == 401
    assert "Invalid" in resp.get_json()["error"]


def test_login_nonexistent_user(client):
    resp = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "pass"})
    assert resp.status_code == 401


def test_me_with_token(client, auth_headers):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["username"] == "testuser"


def test_me_without_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_with_invalid_token(client):
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalidtoken"})
    assert resp.status_code == 401
