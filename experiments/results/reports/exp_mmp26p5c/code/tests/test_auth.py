class TestAuthRegister:
    def test_register_success(self, client):
        resp = client.post("/api/v1/auth/register", json={
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
        assert "password_hash" not in data["user"]

    def test_register_duplicate_username(self, client, registered_user):
        resp = client.post("/api/v1/auth/register", json={
            "username": "testuser",
            "email": "other@example.com",
            "password": "password123",
        })
        assert resp.status_code == 409
        assert "error" in resp.get_json()

    def test_register_duplicate_email(self, client, registered_user):
        resp = client.post("/api/v1/auth/register", json={
            "username": "otheruser",
            "email": "test@example.com",
            "password": "password123",
        })
        assert resp.status_code == 409

    def test_register_validation_short_username(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "username": "ab",
            "email": "ab@example.com",
            "password": "password123",
        })
        assert resp.status_code == 400

    def test_register_validation_short_password(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "username": "validuser",
            "email": "valid@example.com",
            "password": "short",
        })
        assert resp.status_code == 400

    def test_register_validation_invalid_email(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "username": "validuser",
            "email": "not-an-email",
            "password": "password123",
        })
        assert resp.status_code == 400

    def test_register_validation_missing_fields(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "username": "validuser",
        })
        assert resp.status_code == 400


class TestAuthLogin:
    def test_login_success(self, client, registered_user):
        resp = client.post("/api/v1/auth/login", json={
            "username": "testuser",
            "password": "password123",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_wrong_password(self, client, registered_user):
        resp = client.post("/api/v1/auth/login", json={
            "username": "testuser",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "username": "nobody",
            "password": "password123",
        })
        assert resp.status_code == 401

    def test_login_validation_missing(self, client):
        resp = client.post("/api/v1/auth/login", json={"username": "test"})
        assert resp.status_code == 400


class TestAuthRefresh:
    def test_refresh_token(self, client, registered_user):
        refresh_token = registered_user["refresh_token"]
        resp = client.post("/api/v1/auth/refresh", headers={
            "Authorization": f"Bearer {refresh_token}"
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data

    def test_refresh_with_access_token_fails(self, client, registered_user):
        access_token = registered_user["access_token"]
        resp = client.post("/api/v1/auth/refresh", headers={
            "Authorization": f"Bearer {access_token}"
        })
        assert resp.status_code != 200

    def test_refresh_without_token(self, client):
        resp = client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401


class TestAuthMe:
    def test_me_with_valid_token(self, client, registered_user):
        access_token = registered_user["access_token"]
        resp = client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {access_token}"
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["username"] == "testuser"

    def test_me_without_token(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401
