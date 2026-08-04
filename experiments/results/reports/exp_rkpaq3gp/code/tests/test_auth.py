import json


class TestAuthRegister:
    def test_register_success(self, client):
        resp = client.post("/auth/register", json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "password123",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["message"] == "User registered"
        assert data["user"]["username"] == "alice"

    def test_register_missing_fields(self, client):
        resp = client.post("/auth/register", json={"username": "alice"})
        assert resp.status_code == 422
        data = resp.get_json()
        assert data["error"] == "Validation failed"

    def test_register_short_password(self, client):
        resp = client.post("/auth/register", json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "123",
        })
        assert resp.status_code == 422

    def test_register_duplicate_username(self, client, registered_user):
        client.post("/auth/register", json=registered_user)
        resp = client.post("/auth/register", json=registered_user)
        assert resp.status_code == 409
        assert "already taken" in resp.get_json()["error"]

    def test_register_blank_username(self, client):
        resp = client.post("/auth/register", json={
            "username": "   ",
            "email": "alice@example.com",
            "password": "password123",
        })
        assert resp.status_code == 422


class TestAuthLogin:
    def test_login_success(self, client, registered_user):
        client.post("/auth/register", json=registered_user)
        resp = client.post("/auth/login", json={
            "username": "bob",
            "password": "password123",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["username"] == "bob"

    def test_login_wrong_password(self, client, registered_user):
        client.post("/auth/register", json=registered_user)
        resp = client.post("/auth/login", json={
            "username": "bob",
            "password": "wrongpass",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/auth/login", json={
            "username": "ghost",
            "password": "password123",
        })
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/auth/login", json={"username": "bob"})
        assert resp.status_code == 422


class TestAuthRefresh:
    def test_refresh_token(self, client, registered_user):
        client.post("/auth/register", json=registered_user)
        login_resp = client.post("/auth/login", json={
            "username": "bob",
            "password": "password123",
        })
        refresh_token = login_resp.get_json()["refresh_token"]

        resp = client.post("/auth/refresh", headers={
            "Authorization": f"Bearer {refresh_token}"
        })
        assert resp.status_code == 200
        assert "access_token" in resp.get_json()

    def test_refresh_with_access_token(self, client, auth_headers):
        resp = client.post("/auth/refresh", headers=auth_headers)
        assert resp.status_code == 422

    def test_refresh_no_token(self, client):
        resp = client.post("/auth/refresh")
        assert resp.status_code == 401


class TestAuthMe:
    def test_me_authenticated(self, client, auth_headers):
        resp = client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["username"] == "testuser"

    def test_me_unauthenticated(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401
