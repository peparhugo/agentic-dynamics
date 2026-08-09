import pytest


class TestAuthRegister:
    def test_register_success(self, client, db):
        resp = client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "email": "new@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "user" in data
        assert "token" in data
        assert data["user"]["username"] == "newuser"
        assert data["user"]["email"] == "new@example.com"
        assert "id" in data["user"]

    def test_register_duplicate_username(self, client, db):
        client.post(
            "/api/auth/register",
            json={
                "username": "dupuser",
                "email": "dup1@example.com",
                "password": "password123",
            },
        )
        resp = client.post(
            "/api/auth/register",
            json={
                "username": "dupuser",
                "email": "dup2@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 409
        assert "Username already taken" in resp.get_json()["error"]

    def test_register_duplicate_email(self, client, db):
        client.post(
            "/api/auth/register",
            json={
                "username": "user1",
                "email": "dup@example.com",
                "password": "password123",
            },
        )
        resp = client.post(
            "/api/auth/register",
            json={
                "username": "user2",
                "email": "dup@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 409
        assert "Email already registered" in resp.get_json()["error"]

    def test_register_missing_fields(self, client):
        resp = client.post("/api/auth/register", json={})
        assert resp.status_code == 400

        resp = client.post("/api/auth/register", json={"username": "x"})
        assert resp.status_code == 400

        resp = client.post("/api/auth/register", json={"username": "x", "email": "x@x.com"})
        assert resp.status_code == 400

    def test_register_short_password(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"username": "x", "email": "x@x.com", "password": "12345"},
        )
        assert resp.status_code == 400
        assert "at least 6 characters" in resp.get_json()["error"].lower()

    def test_register_no_json(self, client):
        resp = client.post("/api/auth/register", data="not json")
        assert resp.status_code == 400


class TestAuthLogin:
    def test_login_with_username(self, client, user):
        user_data, _ = user
        resp = client.post(
            "/api/auth/login",
            json={"username": user_data["username"], "password": "password123"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data

    def test_login_with_email(self, client, user):
        user_data, _ = user
        resp = client.post(
            "/api/auth/login",
            json={"email": user_data["email"], "password": "password123"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data

    def test_login_invalid_credentials(self, client, user):
        resp = client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "wrongpassword"},
        )
        assert resp.status_code == 401

        resp = client.post(
            "/api/auth/login",
            json={"username": "nonexistent", "password": "password123"},
        )
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/auth/login", json={})
        assert resp.status_code == 400

    def test_login_no_json(self, client):
        resp = client.post("/api/auth/login", data="not json")
        assert resp.status_code == 400


class TestAuthMe:
    def test_me_success(self, client, user, auth_header):
        user_data, _ = user
        resp = client.get("/api/auth/me", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["username"] == user_data["username"]

    def test_me_no_token(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client):
        resp = client.get(
            "/api/auth/me", headers={"Authorization": "Bearer invalidtoken"}
        )
        assert resp.status_code == 401
