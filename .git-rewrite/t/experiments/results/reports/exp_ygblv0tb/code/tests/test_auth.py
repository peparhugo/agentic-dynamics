class TestRegister:
    def test_register_success(self, client, user_payload):
        resp = client.post("/api/v1/auth/register", json=user_payload)
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["user"]["email"] == user_payload["email"]
        assert "password" not in body["user"]
        assert "password_hash" not in body["user"]

    def test_register_duplicate_email(self, client, registered_user):
        resp = client.post("/api/v1/auth/register", json=registered_user)
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "conflict"

    def test_register_invalid_email(self, client):
        resp = client.post("/api/v1/auth/register",
                           json={"email": "not-an-email", "password": "longenough"})
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "validation_error"
        assert "email" in resp.get_json()["error"]["details"]

    def test_register_short_password(self, client):
        resp = client.post("/api/v1/auth/register",
                           json={"email": "a@b.com", "password": "short"})
        assert resp.status_code == 400
        assert "password" in resp.get_json()["error"]["details"]

    def test_register_non_json_body(self, client):
        resp = client.post("/api/v1/auth/register", data="not json",
                           content_type="text/plain")
        assert resp.status_code == 400


class TestLogin:
    def test_login_success(self, client, registered_user):
        resp = client.post("/api/v1/auth/login", json=registered_user)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["token_type"] == "Bearer"

    def test_login_wrong_password(self, client, registered_user):
        resp = client.post("/api/v1/auth/login",
                           json={"email": registered_user["email"],
                                 "password": "wrongpassword"})
        assert resp.status_code == 401

    def test_login_unknown_user(self, client):
        resp = client.post("/api/v1/auth/login",
                           json={"email": "ghost@example.com",
                                 "password": "whatever123"})
        assert resp.status_code == 401


class TestTokens:
    def test_me_returns_current_user(self, client, auth_headers, user_payload):
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["user"]["email"] == user_payload["email"]

    def test_me_requires_token(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "unauthorized"

    def test_me_rejects_garbage_token(self, client):
        resp = client.get("/api/v1/auth/me",
                          headers={"Authorization": "Bearer garbage.token.here"})
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "invalid_token"

    def test_refresh_issues_new_access_token(self, client, tokens):
        resp = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
        assert resp.status_code == 200
        assert resp.get_json()["access_token"]

    def test_access_token_cannot_refresh(self, client, tokens):
        resp = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {tokens['access_token']}"})
        assert resp.status_code == 401
