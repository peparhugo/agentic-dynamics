import pytest


class TestRegister:
    def test_register_success(self, client):
        resp = client.post(
            "/api/v1/auth/register",
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

    def test_register_duplicate_username(self, client, register_user):
        register_user(username="dup", email="dup1@example.com")
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": "dup",
                "email": "dup2@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 409
        assert "already taken" in resp.get_json()["message"]

    def test_register_duplicate_email(self, client, register_user):
        register_user(username="user1", email="dup@example.com")
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": "user2",
                "email": "dup@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 409
        assert "already registered" in resp.get_json()["message"]

    def test_register_missing_fields(self, client):
        resp = client.post("/api/v1/auth/register", json={})
        assert resp.status_code == 422
        data = resp.get_json()
        assert "messages" in data

    def test_register_short_password(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": "user",
                "email": "user@example.com",
                "password": "short",
            },
        )
        assert resp.status_code == 422

    def test_register_short_username(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": "ab",
                "email": "user@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 422

    def test_register_invalid_email(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": "validuser",
                "email": "not-an-email",
                "password": "password123",
            },
        )
        assert resp.status_code == 422

    def test_register_invalid_username_chars(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": "user!name",
                "email": "user@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 422


class TestLogin:
    def test_login_success(self, client, register_user):
        register_user(username="loginuser", password="password123")
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "loginuser", "password": "password123"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_wrong_password(self, client, register_user):
        register_user(username="loginuser", password="correct")
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "loginuser", "password": "wrong"},
        )
        assert resp.status_code == 401
        assert "Invalid" in resp.get_json()["message"]

    def test_login_nonexistent_user(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "password123"},
        )
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422


class TestRefresh:
    def test_refresh_token_success(self, client, register_user):
        resp = register_user()
        refresh_token = resp.get_json()["refresh_token"]
        refresh_resp = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {refresh_token}"},
        )
        assert refresh_resp.status_code == 200
        assert "access_token" in refresh_resp.get_json()

    def test_refresh_with_access_token_fails(self, client, register_user):
        resp = register_user()
        access_token = resp.get_json()["access_token"]
        refresh_resp = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert refresh_resp.status_code in (401, 422)
