from tests.conftest import auth_headers, register_user


class TestRegistration:
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
        register_user(client)
        resp = register_user(client, email="other@example.com")
        assert resp.status_code == 409

    def test_register_duplicate_email(self, client):
        register_user(client)
        resp = register_user(client, username="alice2")
        assert resp.status_code == 409

    def test_register_invalid_email(self, client):
        resp = register_user(client, email="not-an-email")
        assert resp.status_code == 422
        assert "email" in resp.get_json()["details"]

    def test_register_short_password(self, client):
        resp = register_user(client, password="short")
        assert resp.status_code == 422
        assert "password" in resp.get_json()["details"]

    def test_register_short_username(self, client):
        resp = register_user(client, username="ab")
        assert resp.status_code == 422
        assert "username" in resp.get_json()["details"]

    def test_register_missing_fields(self, client):
        resp = client.post("/api/auth/register", json={})
        assert resp.status_code == 422
        details = resp.get_json()["details"]
        assert "username" in details
        assert "email" in details
        assert "password" in details


class TestLogin:
    def test_login_with_username(self, client):
        register_user(client)
        resp = client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
        assert resp.status_code == 200
        assert resp.get_json()["access_token"]

    def test_login_with_email(self, client):
        register_user(client)
        resp = client.post(
            "/api/auth/login", json={"username": "alice@example.com", "password": "password123"}
        )
        assert resp.status_code == 200

    def test_login_wrong_password(self, client):
        register_user(client)
        resp = client.post("/api/auth/login", json={"username": "alice", "password": "wrongpass"})
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/auth/login", json={"username": "ghost", "password": "password123"})
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/auth/login", json={"username": "alice"})
        assert resp.status_code == 400


class TestMe:
    def test_me_requires_auth(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_with_token(self, client, user_token):
        resp = client.get("/api/auth/me", headers=auth_headers(user_token))
        assert resp.status_code == 200
        assert resp.get_json()["username"] == "alice"

    def test_me_invalid_token(self, client):
        resp = client.get("/api/auth/me", headers=auth_headers("garbage.token.value"))
        assert resp.status_code == 401


class TestRefresh:
    def test_refresh_flow(self, client):
        reg = register_user(client)
        refresh_token = reg.get_json()["refresh_token"]
        resp = client.post("/api/auth/refresh", headers=auth_headers(refresh_token))
        assert resp.status_code == 200
        assert resp.get_json()["access_token"]

    def test_refresh_rejects_access_token(self, client, user_token):
        resp = client.post("/api/auth/refresh", headers=auth_headers(user_token))
        assert resp.status_code == 422 or resp.status_code == 401
