import pytest


class TestAuthRegister:

    def test_register_success(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "password123",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert "access_token" in data
        assert data["user"]["username"] == "newuser"
        assert data["user"]["email"] == "new@example.com"
        assert "id" in data["user"]
        assert "password_hash" not in data["user"]

    def test_register_duplicate_username(self, client):
        client.post("/api/auth/register", json={
            "username": "dupuser",
            "email": "dup1@example.com",
            "password": "password123",
        })
        resp = client.post("/api/auth/register", json={
            "username": "dupuser",
            "email": "dup2@example.com",
            "password": "password123",
        })
        assert resp.status_code == 409
        assert "already taken" in resp.get_json()["error"]

    def test_register_duplicate_email(self, client):
        client.post("/api/auth/register", json={
            "username": "emailuser1",
            "email": "same@example.com",
            "password": "password123",
        })
        resp = client.post("/api/auth/register", json={
            "username": "emailuser2",
            "email": "same@example.com",
            "password": "password123",
        })
        assert resp.status_code == 409
        assert "already registered" in resp.get_json()["error"]

    def test_register_missing_fields(self, client):
        resp = client.post("/api/auth/register", json={})
        assert resp.status_code == 422
        data = resp.get_json()
        assert "details" in data
        assert "username" in data["details"]
        assert "email" in data["details"]
        assert "password" in data["details"]

    def test_register_short_password(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "shortpw",
            "email": "short@example.com",
            "password": "123",
        })
        assert resp.status_code == 422
        assert "at least 6" in resp.get_json()["details"]["password"]

    def test_register_empty_username(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "   ",
            "email": "empty@example.com",
            "password": "password123",
        })
        assert resp.status_code == 422

    def test_register_invalid_json(self, client):
        resp = client.post("/api/auth/register", data="not json", content_type="application/json")
        assert resp.status_code == 400


class TestAuthLogin:

    def test_login_success(self, client):
        client.post("/api/auth/register", json={
            "username": "loginuser",
            "email": "login@example.com",
            "password": "password123",
        })
        resp = client.post("/api/auth/login", json={
            "username": "loginuser",
            "password": "password123",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert data["user"]["username"] == "loginuser"

    def test_login_wrong_password(self, client):
        client.post("/api/auth/register", json={
            "username": "wrongpw",
            "email": "wrong@example.com",
            "password": "password123",
        })
        resp = client.post("/api/auth/login", json={
            "username": "wrongpw",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "nobody",
            "password": "password123",
        })
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/auth/login", json={})
        assert resp.status_code == 422

    def test_login_invalid_json(self, client):
        resp = client.post("/api/auth/login", data="bad", content_type="application/json")
        assert resp.status_code == 400
