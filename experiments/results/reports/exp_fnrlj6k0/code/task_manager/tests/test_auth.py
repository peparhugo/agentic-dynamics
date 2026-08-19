import time

import jwt


def test_register_success(client, register_user):
    data = register_user()
    assert data["message"] == "User registered"
    assert data["user"]["username"] == "alice"
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["role"] == "user"
    assert "password" not in data["user"]
    assert data["token"]


def test_register_validates_fields(client):
    response = client.post("/api/auth/register", json={})
    assert response.status_code == 400
    assert response.get_json()["error"] == "username is required"

    response = client.post(
        "/api/auth/register",
        json={"username": "bo", "email": "bob@example.com", "password": "secret123"},
    )
    assert response.status_code == 400
    assert "username" in response.get_json()["error"]

    response = client.post(
        "/api/auth/register",
        json={"username": "bob", "email": "not-an-email", "password": "secret123"},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "email must be a valid email address"

    response = client.post(
        "/api/auth/register",
        json={"username": "bob", "email": "bob@example.com", "password": "123"},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "password must be at least 6 characters"

    response = client.post(
        "/api/auth/register",
        json={"username": "bob", "email": "bob@example.com", "password": "secret123", "role": "superuser"},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "role must be one of: user, admin"


def test_register_duplicate_username(client, register_user):
    register_user()
    response = client.post(
        "/api/auth/register",
        json={"username": "alice", "email": "other@example.com", "password": "secret123"},
    )
    assert response.status_code == 409
    assert response.get_json()["error"] == "username already taken"


def test_register_duplicate_email_case_insensitive(client, register_user):
    register_user()
    response = client.post(
        "/api/auth/register",
        json={"username": "alice2", "email": "ALICE@example.com", "password": "secret123"},
    )
    assert response.status_code == 409
    assert response.get_json()["error"] == "email already registered"


def test_register_admin_role(client, register_user):
    data = register_user(role="admin")
    assert data["user"]["role"] == "admin"


def test_login_success_by_username(client, register_user, login_user):
    register_user()
    response = login_user("alice", "secret123")
    assert response.status_code == 200
    body = response.get_json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["username"] == "alice"


def test_login_success_by_email(client, register_user, login_user):
    register_user()
    response = client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "secret123"}
    )
    assert response.status_code == 200
    assert response.get_json()["access_token"]


def test_login_invalid_credentials(client, register_user, login_user):
    register_user()
    assert login_user("alice", "wrong-password").status_code == 401
    assert login_user("nobody", "secret123").status_code == 401
    assert client.post("/api/auth/login", json={}).status_code == 400


def test_token_is_valid_jwt(client, register_user):
    data = register_user()
    payload = jwt.decode(data["token"], "test-secret", algorithms=["HS256"])
    assert payload["sub"] == str(data["user"]["id"])
    assert payload["type"] == "access"
    assert payload["exp"] > payload["iat"]


def test_me_endpoint(client, register_user, auth_headers):
    data = register_user()
    response = client.get("/api/auth/me", headers=auth_headers(data["token"]))
    assert response.status_code == 200
    assert response.get_json()["user"]["username"] == "alice"


def test_protected_route_without_token(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.get_json()["error"] == "Missing or malformed Authorization header"


def test_protected_route_with_invalid_token(client, auth_headers):
    response = client.get("/api/auth/me", headers=auth_headers("garbage.token.here"))
    assert response.status_code == 401


def test_protected_route_with_expired_token(client, register_user, auth_headers, app):
    data = register_user()
    expired = jwt.encode(
        {
            "sub": str(data["user"]["id"]),
            "type": "access",
            "iat": int(time.time()) - 7200,
            "exp": int(time.time()) - 3600,
        },
        "test-secret",
        algorithm="HS256",
    )
    response = client.get("/api/auth/me", headers=auth_headers(expired))
    assert response.status_code == 401
    assert response.get_json()["error"] == "Token has expired"


def test_protected_route_with_token_for_missing_user(client, auth_headers, app):
    token = jwt.encode(
        {
            "sub": "999999",
            "type": "access",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        },
        "test-secret",
        algorithm="HS256",
    )
    response = client.get("/api/auth/me", headers=auth_headers(token))
    assert response.status_code == 401
    assert "no longer exists" in response.get_json()["error"]


def test_bearer_prefix_required(client, register_user):
    data = register_user()
    response = client.get("/api/auth/me", headers={"Authorization": f"Token {data['token']}"})
    assert response.status_code == 401
