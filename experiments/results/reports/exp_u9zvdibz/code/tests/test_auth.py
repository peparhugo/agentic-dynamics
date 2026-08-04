import json


class TestRegistration:
    def test_register_success(self, client):
        resp = client.post(
            "/auth/register",
            json={"username": "alice", "email": "alice@example.com", "password": "password123"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "token" in data
        assert data["user"]["username"] == "alice"
        assert data["user"]["email"] == "alice@example.com"
        assert "id" in data["user"]

    def test_register_missing_fields(self, client):
        resp = client.post("/auth/register", json={})
        assert resp.status_code == 422
        data = resp.get_json()
        assert "details" in data
        assert "username" in data["details"]
        assert "email" in data["details"]
        assert "password" in data["details"]

    def test_register_short_username(self, client):
        resp = client.post(
            "/auth/register",
            json={"username": "ab", "email": "ab@example.com", "password": "password123"},
        )
        assert resp.status_code == 422

    def test_register_short_password(self, client):
        resp = client.post(
            "/auth/register",
            json={"username": "validuser", "email": "vu@example.com", "password": "12345"},
        )
        assert resp.status_code == 422

    def test_register_invalid_email(self, client):
        resp = client.post(
            "/auth/register",
            json={"username": "validuser", "email": "not-an-email", "password": "password123"},
        )
        assert resp.status_code == 422

    def test_register_duplicate_username(self, auth_client):
        resp = auth_client.post(
            "/auth/register",
            json={"username": "testuser", "email": "other@example.com", "password": "password123"},
        )
        assert resp.status_code == 409

    def test_register_duplicate_email(self, auth_client):
        resp = auth_client.post(
            "/auth/register",
            json={"username": "otheruser", "email": "test@example.com", "password": "password123"},
        )
        assert resp.status_code == 409

    def test_register_no_json(self, client):
        resp = client.post("/auth/register", data="not json", content_type="text/plain")
        assert resp.status_code == 400

    def test_register_whitespace_trimmed(self, client):
        resp = client.post(
            "/auth/register",
            json={"username": "  spaceduser  ", "email": "  SPACED@Example.COM  ", "password": "password123"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["user"]["username"] == "spaceduser"
        assert resp.get_json()["user"]["email"] == "spaced@example.com"


class TestLogin:
    def test_login_success(self, auth_client):
        resp = auth_client.post(
            "/auth/login",
            json={"username": "testuser", "password": "secret123"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data
        assert data["user"]["username"] == "testuser"

    def test_login_wrong_password(self, auth_client):
        resp = auth_client.post(
            "/auth/login",
            json={"username": "testuser", "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post(
            "/auth/login",
            json={"username": "noone", "password": "password"},
        )
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/auth/login", json={})
        assert resp.status_code == 400

    def test_login_no_json(self, client):
        resp = client.post("/auth/login", data="not json", content_type="text/plain")
        assert resp.status_code == 400


class TestMeEndpoint:
    def test_me_authenticated(self, auth_client, headers):
        resp = auth_client.get("/auth/me", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["user"]["username"] == "testuser"

    def test_me_no_token(self, auth_client):
        resp = auth_client.get("/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, auth_client):
        resp = auth_client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401

    def test_me_expired_token(self, auth_client):
        resp = auth_client.get("/auth/me", headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjEsIm5hbWUiOiJ0ZXN0dXNlciIsImlhdCI6MCwiZXhwIjoxfQ.invalidsig"})
        assert resp.status_code == 401

    def test_me_malformed_token(self, auth_client):
        resp = auth_client.get("/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
        assert resp.status_code == 401

    def test_me_wrong_auth_scheme(self, auth_client):
        resp = auth_client.get("/auth/me", headers={"Authorization": "Basic something"})
        assert resp.status_code == 401
