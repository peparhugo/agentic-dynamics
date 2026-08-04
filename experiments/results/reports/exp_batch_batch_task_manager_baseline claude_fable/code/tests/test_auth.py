"""Tests for registration, login and JWT-protected access."""
from tests.conftest import auth_headers, login, register


class TestRegistration:
    def test_register_success(self, client):
        res = register(client, "alice")
        assert res.status_code == 201
        body = res.get_json()
        assert body["user"]["username"] == "alice"
        assert body["user"]["email"] == "alice@example.com"
        assert "access_token" in body
        assert "password" not in body["user"]
        assert "password_hash" not in body["user"]

    def test_register_duplicate_username(self, client):
        register(client, "alice")
        res = register(client, "alice", email="other@example.com")
        assert res.status_code == 409
        assert "Username" in res.get_json()["error"]

    def test_register_duplicate_email(self, client):
        register(client, "alice")
        res = register(client, "alice2", email="alice@example.com")
        assert res.status_code == 409
        assert "Email" in res.get_json()["error"]

    def test_register_missing_fields(self, client):
        res = client.post("/api/auth/register", json={})
        assert res.status_code == 400
        assert "details" in res.get_json()

    def test_register_short_password(self, client):
        res = client.post("/api/auth/register", json={
            "username": "alice", "email": "a@b.com", "password": "short"})
        assert res.status_code == 400

    def test_register_invalid_email(self, client):
        res = client.post("/api/auth/register", json={
            "username": "alice", "email": "not-an-email",
            "password": "password123"})
        assert res.status_code == 400

    def test_register_short_username(self, client):
        res = client.post("/api/auth/register", json={
            "username": "ab", "email": "a@b.com", "password": "password123"})
        assert res.status_code == 400


class TestLogin:
    def test_login_success(self, client):
        register(client, "alice")
        res = login(client, "alice")
        assert res.status_code == 200
        body = res.get_json()
        assert "access_token" in body
        assert body["user"]["username"] == "alice"

    def test_login_with_email(self, client):
        register(client, "alice")
        res = client.post("/api/auth/login", json={
            "username": "alice@example.com", "password": "password123"})
        assert res.status_code == 200

    def test_login_wrong_password(self, client):
        register(client, "alice")
        res = login(client, "alice", password="wrongpassword")
        assert res.status_code == 401

    def test_login_unknown_user(self, client):
        res = login(client, "ghost")
        assert res.status_code == 401

    def test_login_missing_fields(self, client):
        res = client.post("/api/auth/login", json={"username": "alice"})
        assert res.status_code == 400


class TestProtectedRoutes:
    def test_me_returns_current_user(self, client, user_token):
        res = client.get("/api/auth/me", headers=auth_headers(user_token))
        assert res.status_code == 200
        assert res.get_json()["user"]["username"] == "alice"

    def test_me_requires_token(self, client):
        res = client.get("/api/auth/me")
        assert res.status_code == 401

    def test_invalid_token_rejected(self, client):
        res = client.get("/api/auth/me",
                         headers=auth_headers("not.a.real.token"))
        assert res.status_code in (401, 422)

    def test_tasks_require_auth(self, client):
        assert client.get("/api/tasks").status_code == 401
        assert client.post("/api/tasks", json={"title": "x"}).status_code == 401

    def test_categories_require_auth(self, client):
        assert client.get("/api/categories").status_code == 401
