def test_register_success(client):
    resp = client.post("/api/v1/register", json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "password123",
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["message"] == "User registered"
    assert data["user"]["username"] == "newuser"


def test_register_duplicate_email(client):
    client.post("/api/v1/register", json={
        "username": "user1", "email": "dup@example.com", "password": "password123"
    })
    resp = client.post("/api/v1/register", json={
        "username": "user2", "email": "dup@example.com", "password": "password123"
    })
    assert resp.status_code == 409
    assert "Email already registered" in resp.get_json()["error"]


def test_register_duplicate_username(client):
    client.post("/api/v1/register", json={
        "username": "same", "email": "a@example.com", "password": "password123"
    })
    resp = client.post("/api/v1/register", json={
        "username": "same", "email": "b@example.com", "password": "password123"
    })
    assert resp.status_code == 409
    assert "Username already taken" in resp.get_json()["error"]


def test_login_success(client, registered_user):
    resp = client.post("/api/v1/login", json={
        "email": "reg@example.com", "password": "password123"
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert data["token_type"] == "Bearer"


def test_login_invalid_password(client, registered_user):
    resp = client.post("/api/v1/login", json={
        "email": "reg@example.com", "password": "wrongpassword"
    })
    assert resp.status_code == 401


def test_login_nonexistent_user(client):
    resp = client.post("/api/v1/login", json={
        "email": "nobody@example.com", "password": "password123"
    })
    assert resp.status_code == 401


def test_get_profile_authenticated(client, auth_headers):
    resp = client.get("/api/v1/users/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["user"]["username"] == "testuser"


def test_get_profile_unauthenticated(client):
    resp = client.get("/api/v1/users/me")
    assert resp.status_code == 401


def test_update_profile(client, auth_headers):
    resp = client.put("/api/v1/users/me", headers=auth_headers, json={
        "username": "updateduser"
    })
    assert resp.status_code == 200
    assert resp.get_json()["user"]["username"] == "updateduser"


def test_invalid_token(client):
    resp = client.get("/api/v1/users/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code == 401


def test_missing_auth_header(client):
    resp = client.get("/api/v1/users/me")
    assert resp.status_code == 401
