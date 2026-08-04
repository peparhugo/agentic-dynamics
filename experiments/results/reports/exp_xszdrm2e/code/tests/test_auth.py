class TestAuth:
    def test_register_success(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "password": "password123", "name": "New"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "user" in data
        assert "tokens" in data
        assert "access_token" in data["tokens"]
        assert "refresh_token" in data["tokens"]
        assert data["user"]["email"] == "new@example.com"

    def test_register_duplicate_email(self, client):
        client.post(
            "/api/v1/auth/register",
            json={"email": "dup@example.com", "password": "password123", "name": "Dup"},
        )
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "dup@example.com", "password": "password123", "name": "Dup2"},
        )
        assert resp.status_code == 409

    def test_register_validation_error(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "short", "name": ""},
        )
        assert resp.status_code == 422

    def test_login_success(self, client):
        client.post(
            "/api/v1/auth/register",
            json={"email": "login@example.com", "password": "password123", "name": "Login"},
        )
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "login@example.com", "password": "password123"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data["tokens"]

    def test_login_invalid_credentials(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "none@example.com", "password": "wrong"},
        )
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422

    def test_refresh_token(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "refresh@example.com", "password": "password123", "name": "Refresh"},
        )
        refresh_token = resp.get_json()["tokens"]["refresh_token"]

        resp2 = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {refresh_token}"},
        )
        assert resp2.status_code == 200
        assert "access_token" in resp2.get_json()
