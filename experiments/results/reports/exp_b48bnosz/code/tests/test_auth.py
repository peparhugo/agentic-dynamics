class TestRegister:
    def test_register_returns_tokens_and_user(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "password": "s3curepass"},
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["user"]["email"] == "new@example.com"
        assert "access_token" in body and "refresh_token" in body

    def test_duplicate_email_conflict(self, client, user):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "user@example.com", "password": "s3curepass"},
        )
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "email_taken"

    def test_short_password_rejected(self, client):
        resp = client.post(
            "/api/v1/auth/register", json={"email": "a@b.com", "password": "short"}
        )
        assert resp.status_code == 422
        assert "password" in resp.get_json()["error"]["details"]

    def test_invalid_email_rejected(self, client):
        resp = client.post(
            "/api/v1/auth/register", json={"email": "not-an-email", "password": "s3curepass"}
        )
        assert resp.status_code == 422

    def test_non_json_body_rejected(self, client):
        resp = client.post("/api/v1/auth/register", data="email=x", content_type="text/plain")
        assert resp.status_code == 415


class TestLogin:
    def test_login_success(self, client, user):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "password123"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.get_json()

    def test_wrong_password(self, client, user):
        resp = client.post(
            "/api/v1/auth/login", json={"email": "user@example.com", "password": "wrongpass1"}
        )
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "invalid_credentials"

    def test_unknown_user_same_error(self, client):
        resp = client.post(
            "/api/v1/auth/login", json={"email": "ghost@example.com", "password": "whatever1"}
        )
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "invalid_credentials"


class TestProtectedAccess:
    def test_me_requires_token(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "authorization_required"

    def test_me_with_token(self, client, auth):
        resp = client.get("/api/v1/auth/me", headers=auth)
        assert resp.status_code == 200
        assert resp.get_json()["user"]["email"] == "user@example.com"

    def test_garbage_token_rejected(self, client):
        resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "invalid_token"

    def test_refresh_flow(self, client, user):
        tokens = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "password123"},
        ).get_json()
        resp = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
        )
        assert resp.status_code == 200
        new_access = resp.get_json()["access_token"]
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_access}"})
        assert me.status_code == 200

    def test_access_token_cannot_refresh(self, client, auth):
        resp = client.post("/api/v1/auth/refresh", headers=auth)
        assert resp.status_code == 401
