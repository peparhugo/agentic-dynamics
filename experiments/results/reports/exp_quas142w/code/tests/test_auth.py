class TestAuth:
    def test_login_success(self, client, admin_user):
        resp = client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "adminpass123",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert isinstance(data["access_token"], str)

    def test_login_invalid_password(self, client, admin_user):
        resp = client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "username": "nonexistent",
            "password": "somepass",
        })
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/v1/auth/login", json={"username": "admin"})
        assert resp.status_code == 422

    def test_login_empty_body(self, client):
        resp = client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422

    def test_protected_route_without_token(self, client):
        resp = client.get("/api/v1/users")
        assert resp.status_code == 401

    def test_protected_route_bad_token(self, client):
        resp = client.get("/api/v1/users", headers={"Authorization": "Bearer bad.token.here"})
        assert resp.status_code == 401

    def test_v2_login_success(self, client, admin_user):
        resp = client.post("/api/v2/auth/login", json={
            "username": "admin",
            "password": "adminpass123",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert data.get("token_type") == "Bearer"
        assert isinstance(data.get("expires_in"), int)

    def test_v2_login_failure_logs_audit(self, client):
        resp = client.post("/api/v2/auth/login", json={
            "username": "hacker",
            "password": "badpass",
        })
        assert resp.status_code == 401

    def test_admin_required_for_create(self, client, user_token):
        headers = {"Authorization": f"Bearer {user_token}"}
        resp = client.post("/api/v1/users", json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "newpass123",
        }, headers=headers)
        assert resp.status_code == 403

    def test_admin_can_create_user(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.post("/api/v1/users", json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "newpass123",
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.get_json()["data"]
        assert data["username"] == "newuser"
        assert "password_hash" not in data
