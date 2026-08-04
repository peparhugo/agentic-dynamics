import pytest


class TestAuthV1:
    def test_login_success(self, client, sample_user):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "password123"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"
        assert data["user"]["username"] == "testuser"

    def test_login_invalid_credentials(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "wrong"},
        )
        assert resp.status_code == 401
        assert resp.get_json()["code"] == "INVALID_CREDENTIALS"

    def test_login_missing_fields(self, client):
        resp = client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422
        assert resp.get_json()["code"] == "VALIDATION_ERROR"

    def test_login_missing_username(self, client):
        resp = client.post("/api/v1/auth/login", json={"password": "test"})
        assert resp.status_code == 422

    def test_login_missing_password(self, client):
        resp = client.post("/api/v1/auth/login", json={"username": "test"})
        assert resp.status_code == 422

    def test_refresh_success(self, client, sample_user):
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "password123"},
        )
        refresh_token = login_resp.get_json()["refresh_token"]

        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_invalid_token(self, client):
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "invalid"})
        assert resp.status_code == 401

    def test_refresh_access_token_rejected(self, client, sample_user):
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "password123"},
        )
        access_token = login_resp.get_json()["access_token"]

        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
        assert resp.status_code == 401
        assert resp.get_json()["code"] == "INVALID_TOKEN_TYPE"

    def test_login_disabled_account(self, client, sample_user):
        from src.models.user import user_store
        user = user_store.get_by_username("testuser")
        user.is_active = False

        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "password123"},
        )
        assert resp.status_code == 403
        assert resp.get_json()["code"] == "ACCOUNT_DISABLED"

    def test_refresh_disabled_account(self, client, sample_user):
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "password123"},
        )
        refresh_token = login_resp.get_json()["refresh_token"]

        from src.models.user import user_store
        user = user_store.get_by_username("testuser")
        user.is_active = False

        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 404


class TestAuthV2:
    def test_login_v2_wraps_in_data(self, client, sample_user):
        resp = client.post(
            "/api/v2/auth/login",
            json={"username": "testuser", "password": "password123"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "data" in data
        assert "meta" in data
        assert data["meta"]["version"] == "v2"
        assert "access_token" in data["data"]

    def test_refresh_v2_wraps_in_data(self, client, sample_user):
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "password123"},
        )
        refresh_token = login_resp.get_json()["refresh_token"]

        resp = client.post("/api/v2/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "data" in data
        assert data["meta"]["version"] == "v2"

    def test_auth_v1_v2_isolated(self, client):
        resp_v1 = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "password123"},
        ).get_json() if False else None

        client.post(
            "/api/v1/users",
            json={"username": "alice", "email": "alice@test.com", "password": "pass1234"},
        )

        r = client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "pass1234"},
        )
        assert r.status_code == 200
        v1_data = r.get_json()
        assert "data" not in v1_data

        r2 = client.post(
            "/api/v2/auth/login",
            json={"username": "alice", "password": "pass1234"},
        )
        assert r2.status_code == 200
        v2_data = r2.get_json()
        assert "data" in v2_data
        assert v2_data["meta"]["version"] == "v2"
