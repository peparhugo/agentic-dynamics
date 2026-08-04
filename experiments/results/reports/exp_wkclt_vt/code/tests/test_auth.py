import pytest


class TestRegistration:
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
        assert "password_hash" not in data["user"]

    def test_register_duplicate_username(self, client):
        client.post("/api/auth/register", json={
            "username": "dup",
            "email": "a@example.com",
            "password": "password123",
        })
        resp = client.post("/api/auth/register", json={
            "username": "dup",
            "email": "b@example.com",
            "password": "password123",
        })
        assert resp.status_code == 409

    def test_register_duplicate_email(self, client):
        client.post("/api/auth/register", json={
            "username": "user1",
            "email": "dup@example.com",
            "password": "password123",
        })
        resp = client.post("/api/auth/register", json={
            "username": "user2",
            "email": "dup@example.com",
            "password": "password123",
        })
        assert resp.status_code == 409

    def test_register_short_username(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "ab",
            "email": "test@example.com",
            "password": "password123",
        })
        assert resp.status_code == 400

    def test_register_invalid_email(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "testuser",
            "email": "notanemail",
            "password": "password123",
        })
        assert resp.status_code == 400

    def test_register_short_password(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "12345",
        })
        assert resp.status_code == 400

    def test_register_missing_fields(self, client):
        resp = client.post("/api/auth/register", json={})
        assert resp.status_code == 400

    def test_register_no_json(self, client):
        resp = client.post("/api/auth/register", data="not json")
        assert resp.status_code == 400


class TestLogin:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        client.post("/api/auth/register", json={
            "username": "loginuser",
            "email": "login@example.com",
            "password": "password123",
        })

    def test_login_success(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "loginuser",
            "password": "password123",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert data["user"]["username"] == "loginuser"

    def test_login_wrong_password(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "loginuser",
            "password": "wrongpass",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "nobody",
            "password": "password123",
        })
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/auth/login", json={"username": "someone"})
        assert resp.status_code == 400


class TestMeEndpoint:
    def test_me_authenticated(self, client, auth_headers):
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["username"] == "testuser"

    def test_me_no_token(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client):
        resp = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 422
