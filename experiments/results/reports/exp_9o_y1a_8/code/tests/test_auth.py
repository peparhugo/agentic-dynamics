class TestAuthRegister:
    def test_register_success(self, client):
        resp = client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "email": "new@example.com",
                "password": "securepass",
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["user"]["username"] == "newuser"
        assert data["user"]["email"] == "new@example.com"
        assert "token" in data
        assert "password_hash" not in data["user"]

    def test_register_duplicate_username(self, client, auth_headers):
        resp = client.post(
            "/api/auth/register",
            json={
                "username": "testuser",
                "email": "another@example.com",
                "password": "securepass",
            },
        )
        assert resp.status_code == 409
        assert "already taken" in resp.get_json()["error"].lower()

    def test_register_duplicate_email(self, client, auth_headers):
        resp = client.post(
            "/api/auth/register",
            json={
                "username": "another",
                "email": "test@example.com",
                "password": "securepass",
            },
        )
        assert resp.status_code == 409
        assert "already registered" in resp.get_json()["error"].lower()

    def test_register_missing_fields(self, client):
        resp = client.post("/api/auth/register", json={"username": "x"})
        assert resp.status_code == 400
        assert "details" in resp.get_json()

    def test_register_invalid_email(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"username": "xuser", "email": "notanemail", "password": "123456"},
        )
        assert resp.status_code == 400

    def test_register_short_password(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"username": "xuser", "email": "x@x.com", "password": "12345"},
        )
        assert resp.status_code == 400

    def test_register_invalid_username_chars(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"username": "bad user!", "email": "x@x.com", "password": "123456"},
        )
        assert resp.status_code == 400

    def test_register_no_json(self, client):
        resp = client.post("/api/auth/register", data="not json")
        assert resp.status_code == 400


class TestAuthLogin:
    def test_login_success(self, client, auth_headers):
        resp = client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "password123"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["username"] == "testuser"
        assert "token" in data

    def test_login_wrong_password(self, client, auth_headers):
        resp = client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "wrongpass"},
        )
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post(
            "/api/auth/login",
            json={"username": "ghost", "password": "123456"},
        )
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/auth/login", json={})
        assert resp.status_code == 400
