"""Tests for the authentication blueprint."""


class TestRegister:
    def test_register_success(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"username": "alice", "email": "alice@test.com", "password": "pass1234"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["message"] == "user registered"
        assert data["user"]["username"] == "alice"
        assert data["user"]["email"] == "alice@test.com"
        assert "access_token" in data

    def test_register_missing_fields(self, client):
        resp = client.post("/api/auth/register", json={"username": "", "email": "", "password": ""})
        assert resp.status_code == 400
        assert "required" in resp.get_json()["error"]

    def test_register_short_username(self, client):
        resp = client.post("/api/auth/register", json={"username": "ab", "email": "a@b.com", "password": "123456"})
        assert resp.status_code == 400

    def test_register_short_password(self, client):
        resp = client.post("/api/auth/register", json={"username": "validuser", "email": "v@b.com", "password": "12345"})
        assert resp.status_code == 400

    def test_register_invalid_email(self, client):
        resp = client.post("/api/auth/register", json={"username": "validuser", "email": "notanemail", "password": "123456"})
        assert resp.status_code == 400

    def test_register_duplicate_username(self, client):
        client.post("/api/auth/register", json={"username": "alice", "email": "a1@test.com", "password": "pass1234"})
        resp = client.post("/api/auth/register", json={"username": "alice", "email": "a2@test.com", "password": "pass1234"})
        assert resp.status_code == 409

    def test_register_duplicate_email(self, client):
        client.post("/api/auth/register", json={"username": "user1", "email": "dup@test.com", "password": "pass1234"})
        resp = client.post("/api/auth/register", json={"username": "user2", "email": "dup@test.com", "password": "pass1234"})
        assert resp.status_code == 409

    def test_register_email_lowercased(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"username": "bob", "email": "Bob@TEST.Com", "password": "pass1234"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["user"]["email"] == "bob@test.com"

    def test_register_whitespace_trimmed(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"username": "  carl  ", "email": "carl@test.com", "password": "pass1234"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["user"]["username"] == "carl"

    def test_register_not_json(self, client):
        resp = client.post("/api/auth/register", data="plain text", content_type="text/plain")
        assert resp.status_code == 400


class TestLogin:
    def test_login_success(self, client):
        client.post("/api/auth/register", json={"username": "alice", "email": "alice@test.com", "password": "pass1234"})
        resp = client.post("/api/auth/login", json={"email": "alice@test.com", "password": "pass1234"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["message"] == "login successful"
        assert "access_token" in data

    def test_login_wrong_password(self, client):
        client.post("/api/auth/register", json={"username": "alice", "email": "alice@test.com", "password": "pass1234"})
        resp = client.post("/api/auth/login", json={"email": "alice@test.com", "password": "wrongpass"})
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/auth/login", json={"email": "ghost@test.com", "password": "pass1234"})
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/auth/login", json={})
        assert resp.status_code == 400

    def test_login_email_case_insensitive(self, client):
        client.post("/api/auth/register", json={"username": "alice", "email": "alice@test.com", "password": "pass1234"})
        resp = client.post("/api/auth/login", json={"email": "AlIcE@TeSt.CoM", "password": "pass1234"})
        assert resp.status_code == 200


class TestMe:
    def test_me_authenticated(self, client, auth_header):
        resp = client.get("/api/auth/me", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["username"] == "testuser"

    def test_me_no_token(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401
