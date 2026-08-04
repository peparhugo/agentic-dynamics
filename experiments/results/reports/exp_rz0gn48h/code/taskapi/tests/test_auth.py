def test_health_check(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


class TestRegistration:
    def test_register_success(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "secret123",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["message"] == "Registration successful"
        assert data["user"]["username"] == "newuser"
        assert data["user"]["email"] == "new@example.com"
        assert "token" in data
        assert "password" not in data["user"]

    def test_register_duplicate_username(self, client, auth_headers):
        resp = client.post("/api/auth/register", json={
            "username": "testuser",
            "email": "another@example.com",
            "password": "secret123",
        })
        assert resp.status_code == 409
        assert "already taken" in resp.get_json()["error"]

    def test_register_duplicate_email(self, client, auth_headers):
        resp = client.post("/api/auth/register", json={
            "username": "anotheruser",
            "email": "test@example.com",
            "password": "secret123",
        })
        assert resp.status_code == 409

    def test_register_short_username(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "ab",
            "email": "ab@example.com",
            "password": "secret123",
        })
        assert resp.status_code == 422
        assert "details" in resp.get_json()
        assert "username" in resp.get_json()["details"]

    def test_register_invalid_email(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "validuser",
            "email": "notanemail",
            "password": "secret123",
        })
        assert resp.status_code == 422

    def test_register_short_password(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "validuser",
            "email": "valid@example.com",
            "password": "12345",
        })
        assert resp.status_code == 422

    def test_register_missing_fields(self, client):
        resp = client.post("/api/auth/register", json={})
        assert resp.status_code == 422

    def test_register_non_json(self, client):
        resp = client.post("/api/auth/register", data="not json")
        assert resp.status_code == 400


class TestLogin:
    def test_login_with_username(self, client, auth_headers):
        resp = client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "password123",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["message"] == "Login successful"
        assert "token" in data

    def test_login_with_email(self, client, auth_headers):
        resp = client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "password123",
        })
        assert resp.status_code == 200
        assert "token" in resp.get_json()

    def test_login_wrong_password(self, client, auth_headers):
        resp = client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "nobody",
            "password": "password123",
        })
        assert resp.status_code == 401

    def test_login_missing_credentials(self, client):
        resp = client.post("/api/auth/login", json={})
        assert resp.status_code == 400


class TestProfile:
    def test_me_authenticated(self, client, auth_headers):
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        user = resp.get_json()["user"]
        assert user["username"] == "testuser"
        assert user["email"] == "test@example.com"
        assert "password_hash" not in user

    def test_me_no_token(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client):
        resp = client.get("/api/auth/me", headers={
            "Authorization": "Bearer invalid.token.here"
        })
        assert resp.status_code == 401

    def test_me_expired_token(self, client, app):
        import datetime
        import jwt
        from taskapi.config import TestConfig

        payload = {
            "sub": 999,
            "iat": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5),
            "exp": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1),
        }
        token = jwt.encode(payload, TestConfig.JWT_SECRET, algorithm=TestConfig.JWT_ALGORITHM)
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401
        assert "expired" in resp.get_json()["error"].lower()
