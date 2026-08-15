import time
from datetime import datetime, timedelta, timezone

import jwt


def test_register_success(client):
    response = client.post(
        "/api/auth/register",
        json={"username": "carol", "email": "carol@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["token"]
    assert body["user"]["username"] == "carol"
    assert body["user"]["email"] == "carol@example.com"
    assert "password" not in body["user"]


def test_register_duplicate_username(client):
    client.post("/api/auth/register", json={"username": "dave", "email": "dave@example.com", "password": "password123"})
    response = client.post(
        "/api/auth/register",
        json={"username": "dave", "email": "dave2@example.com", "password": "password123"},
    )
    assert response.status_code == 409
    assert response.get_json()["error"]


def test_register_duplicate_email(client):
    client.post("/api/auth/register", json={"username": "erin", "email": "erin@example.com", "password": "password123"})
    response = client.post(
        "/api/auth/register",
        json={"username": "erin2", "email": "erin@example.com", "password": "password123"},
    )
    assert response.status_code == 409


def test_register_missing_fields(client):
    response = client.post("/api/auth/register", json={})
    assert response.status_code == 400
    assert "username" in response.get_json()["errors"]


def test_register_short_password(client):
    response = client.post(
        "/api/auth/register",
        json={"username": "frank", "email": "frank@example.com", "password": "short"},
    )
    assert response.status_code == 400
    assert "password" in response.get_json()["errors"]


def test_register_case_insensitive_duplicate(client):
    client.post("/api/auth/register", json={"username": "grace", "email": "Grace@Example.com", "password": "password123"})
    response = client.post(
        "/api/auth/register",
        json={"username": "grace2", "email": "grace@example.com", "password": "password123"},
    )
    assert response.status_code == 409


def test_login_success_by_username(client):
    client.post("/api/auth/register", json={"username": "heidi", "email": "heidi@example.com", "password": "password123"})
    response = client.post("/api/auth/login", json={"identifier": "heidi", "password": "password123"})
    assert response.status_code == 200
    assert response.get_json()["token"]


def test_login_success_by_email(client):
    client.post("/api/auth/register", json={"username": "ivan", "email": "ivan@example.com", "password": "password123"})
    response = client.post("/api/auth/login", json={"identifier": "ivan@example.com", "password": "password123"})
    assert response.status_code == 200


def test_login_wrong_password(client):
    client.post("/api/auth/register", json={"username": "judy", "email": "judy@example.com", "password": "password123"})
    response = client.post("/api/auth/login", json={"identifier": "judy", "password": "wrongpassword"})
    assert response.status_code == 401


def test_login_unknown_user(client):
    response = client.post("/api/auth/login", json={"identifier": "nobody", "password": "password123"})
    assert response.status_code == 401


def test_login_missing_credentials(client):
    response = client.post("/api/auth/login", json={})
    assert response.status_code == 400


def test_me_returns_current_user(auth_client):
    response = auth_client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.get_json()["username"] == "alice"


def test_protected_endpoint_without_token(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_protected_endpoint_with_invalid_token(client):
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_protected_endpoint_with_malformed_header(client):
    response = client.get("/api/auth/me", headers={"Authorization": "Basic abc"})
    assert response.status_code == 401


def test_protected_endpoint_with_expired_token(client):
    client.post("/api/auth/register", json={"username": "mallory", "email": "mallory@example.com", "password": "password123"})
    expired = jwt.encode(
        {
            "sub": 1,
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        "test-secret",
        algorithm="HS256",
    )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_token_with_wrong_secret(client):
    forged = jwt.encode({"sub": 1}, "wrong-secret", algorithm="HS256")
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_token_for_nonexistent_user(client):
    token = jwt.encode({"sub": 9999}, "test-secret", algorithm="HS256")
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
