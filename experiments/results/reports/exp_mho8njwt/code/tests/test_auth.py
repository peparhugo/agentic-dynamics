import json
import pytest

from tests.helpers import register_user, login_user, get_auth_header


class TestAuth:
    def test_register_success(self, client, db):
        resp = register_user(client, "newuser", "password123")
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["message"] == "User registered successfully"
        assert data["user"]["username"] == "newuser"

    def test_register_duplicate_username(self, client, db):
        register_user(client, "dupeuser", "password123")
        resp = register_user(client, "dupeuser", "password123")
        assert resp.status_code == 409
        assert "already exists" in resp.get_json()["error"]

    def test_register_short_username(self, client, db):
        resp = register_user(client, "ab", "password123")
        assert resp.status_code == 422
        assert "Validation failed" in resp.get_json()["error"]

    def test_register_short_password(self, client, db):
        resp = register_user(client, "validuser", "short")
        assert resp.status_code == 422
        assert "Validation failed" in resp.get_json()["error"]

    def test_register_missing_fields(self, client, db):
        resp = client.post(
            "/v1/auth/register",
            data=json.dumps({"username": "x"}),
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_login_success(self, client, db):
        register_user(client, "loginuser", "password123")
        resp = login_user(client, "loginuser", "password123")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"

    def test_login_invalid_password(self, client, db):
        register_user(client, "loginuser2", "password123")
        resp = login_user(client, "loginuser2", "wrongpass")
        assert resp.status_code == 401
        assert "Invalid" in resp.get_json()["error"]

    def test_login_nonexistent_user(self, client, db):
        resp = login_user(client, "nobody", "password123")
        assert resp.status_code == 401

    def test_login_missing_fields(self, client, db):
        resp = client.post(
            "/v1/auth/login",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_refresh_token(self, client, db):
        register_user(client, "refreshuser", "password123")
        login_resp = login_user(client, "refreshuser", "password123")
        tokens = login_resp.get_json()

        resp = client.post(
            "/v1/auth/refresh",
            headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
        )
        assert resp.status_code == 200
        new_tokens = resp.get_json()
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens

    def test_refresh_invalid_token(self, client, db):
        resp = client.post(
            "/v1/auth/refresh",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert resp.status_code == 422

    def test_logout(self, client, db):
        register_user(client, "logoutuser", "password123")
        auth_header = get_auth_header(client)
        resp = client.post("/v1/auth/logout", headers=auth_header)
        assert resp.status_code == 200
        assert resp.get_json()["message"] == "Logged out successfully"

    def test_protected_route_no_token(self, client, db):
        resp = client.get("/v1/users")
        assert resp.status_code == 401

    def test_protected_route_invalid_token(self, client, db):
        resp = client.get(
            "/v1/users", headers={"Authorization": "Bearer bad.token.here"}
        )
        assert resp.status_code == 422
