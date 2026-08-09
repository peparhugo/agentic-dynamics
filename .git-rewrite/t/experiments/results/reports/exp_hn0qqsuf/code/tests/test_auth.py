import time


class TestAuthEndpoints:
    def test_register_success(self, client):
        resp = client.post("/v1/auth/register", json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "password123",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["username"] == "newuser"
        assert data["user"]["email"] == "new@example.com"

    def test_register_missing_fields(self, client):
        resp = client.post("/v1/auth/register", json={"username": "x"})
        assert resp.status_code == 422
        data = resp.get_json()
        assert data["error"] == "Validation failed"

    def test_register_duplicate_username(self, client):
        client.post("/v1/auth/register", json={
            "username": "dupuser", "email": "a@example.com", "password": "password123",
        })
        resp = client.post("/v1/auth/register", json={
            "username": "dupuser", "email": "b@example.com", "password": "password123",
        })
        assert resp.status_code == 409

    def test_register_duplicate_email(self, client):
        client.post("/v1/auth/register", json={
            "username": "user1", "email": "dup@example.com", "password": "password123",
        })
        resp = client.post("/v1/auth/register", json={
            "username": "user2", "email": "dup@example.com", "password": "password123",
        })
        assert resp.status_code == 409

    def test_register_invalid_email(self, client):
        resp = client.post("/v1/auth/register", json={
            "username": "user1", "email": "notanemail", "password": "password123",
        })
        assert resp.status_code == 422

    def test_register_short_password(self, client):
        resp = client.post("/v1/auth/register", json={
            "username": "user1", "email": "a@example.com", "password": "short",
        })
        assert resp.status_code == 422

    def test_register_invalid_json(self, client):
        resp = client.post("/v1/auth/register", data="not json", content_type="application/json")
        assert resp.status_code == 400

    def test_login_success(self, client):
        client.post("/v1/auth/register", json={
            "username": "loginuser", "email": "login@example.com", "password": "password123",
        })
        resp = client.post("/v1/auth/login", json={
            "email": "login@example.com", "password": "password123",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_invalid_credentials(self, client):
        resp = client.post("/v1/auth/login", json={
            "email": "nonexistent@example.com", "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_login_wrong_password(self, client):
        client.post("/v1/auth/register", json={
            "username": "pwuser", "email": "pw@example.com", "password": "password123",
        })
        resp = client.post("/v1/auth/login", json={
            "email": "pw@example.com", "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_login_rate_limit(self, client):
        for _ in range(5):
            client.post("/v1/auth/login", json={
                "email": "test@example.com", "password": "wrong",
            })
        resp = client.post("/v1/auth/login", json={
            "email": "test@example.com", "password": "wrong",
        })
        assert resp.status_code == 429

    def test_refresh_token_success(self, client):
        client.post("/v1/auth/register", json={
            "username": "refresher", "email": "refresh@example.com", "password": "password123",
        })
        login_resp = client.post("/v1/auth/login", json={
            "email": "refresh@example.com", "password": "password123",
        })
        refresh_token = login_resp.get_json()["refresh_token"]

        resp = client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_token_invalid(self, client):
        resp = client.post("/v1/auth/refresh", json={"refresh_token": "invalid.token.here"})
        assert resp.status_code == 401

    def test_refresh_token_reuse(self, client):
        client.post("/v1/auth/register", json={
            "username": "reuser", "email": "reuse@example.com", "password": "password123",
        })
        login_resp = client.post("/v1/auth/login", json={
            "email": "reuse@example.com", "password": "password123",
        })
        refresh_token = login_resp.get_json()["refresh_token"]

        client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
        resp = client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 401

    def test_logout(self, client, auth_headers):
        resp = client.post("/v1/auth/logout", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["message"] == "Logged out successfully"

    def test_protected_route_without_token(self, client):
        resp = client.get("/v1/users")
        assert resp.status_code == 401

    def test_protected_route_invalid_token(self, client):
        resp = client.get("/v1/users", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code == 401

    def test_protected_route_wrong_token_type(self, client):
        client.post("/v1/auth/register", json={
            "username": "typeuser", "email": "type@example.com", "password": "password123",
        })
        login_resp = client.post("/v1/auth/login", json={
            "email": "type@example.com", "password": "password123",
        })
        refresh_token = login_resp.get_json()["refresh_token"]
        resp = client.get("/v1/users", headers={"Authorization": f"Bearer {refresh_token}"})
        assert resp.status_code == 401
