import pytest


class TestRegistration:
    def test_register_success(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["user"]["username"] == "alice"
        assert data["user"]["email"] == "alice@example.com"
        assert "access_token" in data

    def test_register_duplicate_username(self, client):
        client.post(
            "/api/auth/register",
            json={"username": "alice", "email": "alice@a.com", "password": "secret123"},
        )
        resp = client.post(
            "/api/auth/register",
            json={"username": "alice", "email": "alice@b.com", "password": "secret123"},
        )
        assert resp.status_code == 409
        assert resp.get_json()["error"] == "username already taken"

    def test_register_duplicate_email(self, client):
        client.post(
            "/api/auth/register",
            json={"username": "bob", "email": "bob@example.com", "password": "secret123"},
        )
        resp = client.post(
            "/api/auth/register",
            json={"username": "bobby", "email": "bob@example.com", "password": "secret123"},
        )
        assert resp.status_code == 409
        assert resp.get_json()["error"] == "email already registered"

    def test_register_missing_fields(self, client):
        resp = client.post("/api/auth/register", json={"username": "x"})
        assert resp.status_code == 400
        assert "required" in resp.get_json()["error"]

    def test_register_short_username(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"username": "ab", "email": "ab@example.com", "password": "secret123"},
        )
        assert resp.status_code == 400

    def test_register_short_password(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"username": "validuser", "email": "v@example.com", "password": "12345"},
        )
        assert resp.status_code == 400

    def test_register_invalid_email(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"username": "validuser", "email": "notanemail", "password": "secret123"},
        )
        assert resp.status_code == 400

    def test_register_no_json_body(self, client):
        resp = client.post("/api/auth/register", data="not json", content_type="text/plain")
        assert resp.status_code == 400


class TestLogin:
    def _register(self, client):
        return client.post(
            "/api/auth/register",
            json={"username": "charlie", "email": "charlie@example.com", "password": "mypassword"},
        )

    def test_login_with_username(self, client):
        self._register(client)
        resp = client.post(
            "/api/auth/login",
            json={"username": "charlie", "password": "mypassword"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["username"] == "charlie"
        assert "access_token" in data

    def test_login_with_email(self, client):
        self._register(client)
        resp = client.post(
            "/api/auth/login",
            json={"username": "charlie@example.com", "password": "mypassword"},
        )
        assert resp.status_code == 200

    def test_login_wrong_password(self, client):
        self._register(client)
        resp = client.post(
            "/api/auth/login",
            json={"username": "charlie", "password": "wrongpass"},
        )
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post(
            "/api/auth/login",
            json={"username": "ghost", "password": "nope"},
        )
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/auth/login", json={"username": "x"})
        assert resp.status_code == 400


class TestMeEndpoint:
    def test_me_authenticated(self, client, auth_headers):
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["user"]["username"] == "testuser"

    def test_me_unauthenticated(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401
