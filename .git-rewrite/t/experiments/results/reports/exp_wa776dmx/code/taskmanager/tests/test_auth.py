"""Tests for authentication endpoints."""

import json


class TestRegister:
    def test_register_success(self, client):
        resp = client.post(
            "/api/auth/register",
            data=json.dumps({
                "username": "testuser",
                "email": "test@example.com",
                "password": "securepass123",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["message"] == "User registered successfully"
        assert data["user"]["username"] == "testuser"
        assert data["user"]["email"] == "test@example.com"
        assert "access_token" in data
        assert "refresh_token" in data
        assert "password" not in data["user"]
        assert "password_hash" not in data["user"]

    def test_register_missing_field(self, client):
        resp = client.post(
            "/api/auth/register",
            data=json.dumps({"username": "test"}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "Missing required field" in resp.get_json()["error"]

    def test_register_duplicate_username(self, client):
        client.post(
            "/api/auth/register",
            data=json.dumps({
                "username": "user",
                "email": "a@b.com",
                "password": "pass",
            }),
            content_type="application/json",
        )
        resp = client.post(
            "/api/auth/register",
            data=json.dumps({
                "username": "user",
                "email": "other@b.com",
                "password": "pass",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 409
        assert "Username already taken" in resp.get_json()["error"]

    def test_register_duplicate_email(self, client):
        client.post(
            "/api/auth/register",
            data=json.dumps({
                "username": "user1",
                "email": "dup@b.com",
                "password": "pass",
            }),
            content_type="application/json",
        )
        resp = client.post(
            "/api/auth/register",
            data=json.dumps({
                "username": "user2",
                "email": "dup@b.com",
                "password": "pass",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 409
        assert "Email already registered" in resp.get_json()["error"]


class TestLogin:
    def test_login_success(self, client):
        client.post(
            "/api/auth/register",
            data=json.dumps({
                "username": "loginuser",
                "email": "login@example.com",
                "password": "mypassword",
            }),
            content_type="application/json",
        )
        resp = client.post(
            "/api/auth/login",
            data=json.dumps({
                "username": "loginuser",
                "password": "mypassword",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["message"] == "Login successful"
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_wrong_password(self, client):
        client.post(
            "/api/auth/register",
            data=json.dumps({
                "username": "pwuser",
                "email": "pw@example.com",
                "password": "correctpass",
            }),
            content_type="application/json",
        )
        resp = client.post(
            "/api/auth/login",
            data=json.dumps({
                "username": "pwuser",
                "password": "wrongpass",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 401
        assert "Invalid username or password" in resp.get_json()["error"]

    def test_login_nonexistent_user(self, client):
        resp = client.post(
            "/api/auth/login",
            data=json.dumps({
                "username": "noone",
                "password": "pass",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post(
            "/api/auth/login",
            data=json.dumps({"username": "noone"}),
            content_type="application/json",
        )
        assert resp.status_code == 400


class TestTokenRefresh:
    def test_refresh_token(self, client):
        register_resp = client.post(
            "/api/auth/register",
            data=json.dumps({
                "username": "refreshuser",
                "email": "refresh@example.com",
                "password": "pass",
            }),
            content_type="application/json",
        )
        refresh_token = register_resp.get_json()["refresh_token"]
        resp = client.post(
            "/api/auth/refresh",
            headers={"Authorization": f"Bearer {refresh_token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data

    def test_refresh_with_access_token_fails(self, client):
        register_resp = client.post(
            "/api/auth/register",
            data=json.dumps({
                "username": "refresh2",
                "email": "refresh2@example.com",
                "password": "pass",
            }),
            content_type="application/json",
        )
        access_token = register_resp.get_json()["access_token"]
        resp = client.post(
            "/api/auth/refresh",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 422


class TestMe:
    def test_me_authenticated(self, client):
        register_resp = client.post(
            "/api/auth/register",
            data=json.dumps({
                "username": "meuser",
                "email": "me@example.com",
                "password": "pass",
            }),
            content_type="application/json",
        )
        access_token = register_resp.get_json()["access_token"]
        resp = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["username"] == "meuser"
        assert data["user"]["email"] == "me@example.com"

    def test_me_unauthenticated(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client):
        resp = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalidtoken123"},
        )
        assert resp.status_code == 422
