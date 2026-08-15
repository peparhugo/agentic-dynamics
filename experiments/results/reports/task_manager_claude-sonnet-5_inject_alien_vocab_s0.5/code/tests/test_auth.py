import pytest

from tests.conftest import register_user, auth_header


class TestRegister:
    def test_register_success(self, client):
        resp = register_user(client)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["user"]["username"] == "alice"
        assert data["user"]["email"] == "alice@example.com"
        assert "password" not in data["user"]
        assert "password_hash" not in data["user"]
        assert data["access_token"]
        assert data["refresh_token"]

    def test_register_duplicate_username(self, client):
        register_user(client, "alice", "alice@example.com")
        resp = register_user(client, "alice", "other@example.com")
        assert resp.status_code == 409

    def test_register_duplicate_email(self, client):
        register_user(client, "alice", "alice@example.com")
        resp = register_user(client, "alice2", "alice@example.com")
        assert resp.status_code == 409

    @pytest.mark.parametrize(
        "payload",
        [
            {"username": "ab", "email": "a@b.com", "password": "password123"},
            {"username": "validname", "email": "not-an-email", "password": "password123"},
            {"username": "validname", "email": "a@b.com", "password": "short"},
            {"username": "", "email": "", "password": ""},
        ],
    )
    def test_register_validation_errors(self, client, payload):
        resp = client.post("/api/auth/register", json=payload)
        assert resp.status_code == 400
        assert "details" in resp.get_json()


class TestLogin:
    def test_login_with_username(self, client):
        register_user(client)
        resp = client.post(
            "/api/auth/login", json={"username": "alice", "password": "password123"}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["access_token"]

    def test_login_with_email(self, client):
        register_user(client)
        resp = client.post(
            "/api/auth/login",
            json={"email": "alice@example.com", "password": "password123"},
        )
        assert resp.status_code == 200

    def test_login_wrong_password(self, client):
        register_user(client)
        resp = client.post(
            "/api/auth/login", json={"username": "alice", "password": "wrongpass"}
        )
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post(
            "/api/auth/login", json={"username": "ghost", "password": "password123"}
        )
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/auth/login", json={"username": "alice"})
        assert resp.status_code == 400


class TestMeAndRefresh:
    def test_me_requires_auth(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_returns_current_user(self, client, user_alice):
        resp = client.get("/api/auth/me", headers=user_alice["headers"])
        assert resp.status_code == 200
        assert resp.get_json()["user"]["username"] == "alice"

    def test_me_with_invalid_token(self, client):
        resp = client.get("/api/auth/me", headers=auth_header("not-a-real-token"))
        assert resp.status_code == 422

    def test_refresh_returns_new_access_token(self, client, user_alice):
        resp = client.post(
            "/api/auth/refresh",
            headers=auth_header(user_alice["refresh_token"]),
        )
        assert resp.status_code == 200
        assert resp.get_json()["access_token"]

    def test_refresh_rejects_access_token(self, client, user_alice):
        resp = client.post("/api/auth/refresh", headers=user_alice["headers"])
        assert resp.status_code == 422

    def test_list_users_requires_auth(self, client):
        resp = client.get("/api/auth/users")
        assert resp.status_code == 401

    def test_list_users(self, client, user_alice, user_bob):
        resp = client.get("/api/auth/users", headers=user_alice["headers"])
        assert resp.status_code == 200
        usernames = {u["username"] for u in resp.get_json()["users"]}
        assert {"alice", "bob"} <= usernames
