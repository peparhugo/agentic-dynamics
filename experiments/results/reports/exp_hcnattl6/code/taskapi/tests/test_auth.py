class TestAuthRegister:
    def test_register_success(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "securepass",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert "user" in data
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["username"] == "alice"
        assert data["user"]["email"] == "alice@example.com"
        assert "password" not in data["user"]
        assert "password_hash" not in data["user"]

    def test_register_duplicate_username(self, client):
        client.post("/api/auth/register", json={
            "username": "bob", "email": "bob1@example.com", "password": "pass123456",
        })
        resp = client.post("/api/auth/register", json={
            "username": "bob", "email": "bob2@example.com", "password": "pass123456",
        })
        assert resp.status_code == 409
        data = resp.get_json()
        assert "username" in data.get("details", {})

    def test_register_duplicate_email(self, client):
        client.post("/api/auth/register", json={
            "username": "carol1", "email": "carol@example.com", "password": "pass123456",
        })
        resp = client.post("/api/auth/register", json={
            "username": "carol2", "email": "carol@example.com", "password": "pass123456",
        })
        assert resp.status_code == 409
        data = resp.get_json()
        assert "email" in data.get("details", {})

    def test_register_short_username(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "ab", "email": "short@example.com", "password": "pass123456",
        })
        assert resp.status_code == 400
        assert "username" in resp.get_json().get("details", {})

    def test_register_invalid_email(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "validuser", "email": "notanemail", "password": "pass123456",
        })
        assert resp.status_code == 400
        assert "email" in resp.get_json().get("details", {})

    def test_register_short_password(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "validuser", "email": "valid@example.com", "password": "12345",
        })
        assert resp.status_code == 400
        assert "password" in resp.get_json().get("details", {})

    def test_register_missing_fields(self, client):
        resp = client.post("/api/auth/register", json={})
        assert resp.status_code == 400
        assert "details" in resp.get_json()


class TestAuthLogin:
    def test_login_with_username(self, client):
        client.post("/api/auth/register", json={
            "username": "dave", "email": "dave@example.com", "password": "pass123456",
        })
        resp = client.post("/api/auth/login", json={
            "username": "dave", "password": "pass123456",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["username"] == "dave"

    def test_login_with_email(self, client):
        client.post("/api/auth/register", json={
            "username": "eve", "email": "eve@example.com", "password": "pass123456",
        })
        resp = client.post("/api/auth/login", json={
            "username": "eve@example.com", "password": "pass123456",
        })
        assert resp.status_code == 200

    def test_login_wrong_password(self, client):
        client.post("/api/auth/register", json={
            "username": "frank", "email": "frank@example.com", "password": "pass123456",
        })
        resp = client.post("/api/auth/login", json={
            "username": "frank", "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "ghost", "password": "whatever",
        })
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/auth/login", json={})
        assert resp.status_code == 400


class TestAuthToken:
    def test_refresh_token(self, client):
        reg = client.post("/api/auth/register", json={
            "username": "grace", "email": "grace@example.com", "password": "pass123456",
        })
        refresh_token = reg.get_json()["refresh_token"]
        resp = client.post("/api/auth/refresh", headers={
            "Authorization": f"Bearer {refresh_token}",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.get_json()

    def test_refresh_with_access_token_fails(self, client):
        reg = client.post("/api/auth/register", json={
            "username": "heidi", "email": "heidi@example.com", "password": "pass123456",
        })
        access_token = reg.get_json()["access_token"]
        resp = client.post("/api/auth/refresh", headers={
            "Authorization": f"Bearer {access_token}",
        })
        assert resp.status_code == 422

    def test_me_endpoint(self, client, auth_headers):
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["username"] == "testuser"

    def test_me_without_token(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_protected_route_without_token(self, client):
        resp = client.get("/api/tasks")
        assert resp.status_code == 401
