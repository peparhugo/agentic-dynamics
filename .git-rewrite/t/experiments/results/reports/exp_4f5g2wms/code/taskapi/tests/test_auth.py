class TestRegister:
    def test_register_success(self, client):
        resp = client.post(
            "/auth/register",
            json={
                "username": "newuser",
                "email": "new@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["user"]["username"] == "newuser"
        assert data["user"]["email"] == "new@example.com"
        assert "token" in data
        assert "password_hash" not in data["user"]

    def test_register_missing_fields(self, client):
        resp = client.post("/auth/register", json={"username": "test"})
        assert resp.status_code == 400
        assert "Missing required fields" in resp.get_json()["error"]

        resp = client.post("/auth/register", json={})
        assert resp.status_code == 400

    def test_register_short_username(self, client):
        resp = client.post(
            "/auth/register",
            json={"username": "ab", "email": "test@test.com", "password": "password123"},
        )
        assert resp.status_code == 400
        assert "username must be at least 3 characters" in resp.get_json()["error"]

    def test_register_short_password(self, client):
        resp = client.post(
            "/auth/register",
            json={"username": "testuser", "email": "test@test.com", "password": "12345"},
        )
        assert resp.status_code == 400
        assert "password must be at least 6 characters" in resp.get_json()["error"]

    def test_register_invalid_email(self, client):
        resp = client.post(
            "/auth/register",
            json={"username": "testuser", "email": "bademail", "password": "password123"},
        )
        assert resp.status_code == 400
        assert "Invalid email" in resp.get_json()["error"]

    def test_register_duplicate_username(self, client, auth_tokens):
        resp = client.post(
            "/auth/register",
            json={
                "username": "alice",
                "email": "different@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 409
        assert "already exists" in resp.get_json()["error"]

    def test_register_duplicate_email(self, client, auth_tokens):
        resp = client.post(
            "/auth/register",
            json={
                "username": "different_user",
                "email": "alice@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 409
        assert "already exists" in resp.get_json()["error"]

    def test_register_empty_username(self, client):
        resp = client.post(
            "/auth/register",
            json={"username": "   ", "email": "test@test.com", "password": "password123"},
        )
        assert resp.status_code == 400

    def test_register_not_json(self, client):
        resp = client.post("/auth/register", data="not json")
        assert resp.status_code == 400
        assert "JSON" in resp.get_json()["error"]


class TestLogin:
    def test_login_with_username(self, client, auth_tokens):
        resp = client.post(
            "/auth/login",
            json={"username": "alice", "password": "password123"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["username"] == "alice"
        assert "token" in data

    def test_login_with_email(self, client, auth_tokens):
        resp = client.post(
            "/auth/login",
            json={"username": "alice@example.com", "password": "password123"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["user"]["username"] == "alice"

    def test_login_wrong_password(self, client, auth_tokens):
        resp = client.post(
            "/auth/login",
            json={"username": "alice", "password": "wrongpassword"},
        )
        assert resp.status_code == 401
        assert "Invalid" in resp.get_json()["error"]

    def test_login_nonexistent_user(self, client):
        resp = client.post(
            "/auth/login",
            json={"username": "nobody", "password": "password123"},
        )
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/auth/login", json={"username": "alice"})
        assert resp.status_code == 400


class TestMe:
    def test_me_authenticated(self, client, auth_header, auth_tokens):
        resp = client.get("/auth/me", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["username"] == "alice"
        assert data["user"]["email"] == "alice@example.com"
        assert "created_at" in data["user"]

    def test_me_no_token(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client):
        resp = client.get(
            "/auth/me", headers={"Authorization": "Bearer invalid-token"}
        )
        assert resp.status_code == 401

    def test_me_malformed_header(self, client):
        resp = client.get("/auth/me", headers={"Authorization": "NoBearer token"})
        assert resp.status_code == 401
