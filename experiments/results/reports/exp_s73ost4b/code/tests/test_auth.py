class TestAuth:
    def test_register_success(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "name": "John", "email": "john@example.com", "password": "secret123"
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert "token" in data
        assert data["user"]["email"] == "john@example.com"
        assert data["user"]["role"] == "user"
        assert "password" not in data["user"]

    def test_register_duplicate_email(self, client):
        client.post("/api/v1/auth/register", json={
            "name": "A", "email": "dup@example.com", "password": "secret123"
        })
        resp = client.post("/api/v1/auth/register", json={
            "name": "B", "email": "dup@example.com", "password": "secret456"
        })
        assert resp.status_code == 409
        assert "already registered" in resp.get_json()["error"]

    def test_register_validation_missing_name(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "x@example.com", "password": "secret123"
        })
        assert resp.status_code == 422
        assert "name" in resp.get_json().get("details", {})

    def test_register_validation_short_password(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "name": "X", "email": "x@example.com", "password": "ab"
        })
        assert resp.status_code == 422

    def test_register_validation_bad_email(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "name": "X", "email": "not-email", "password": "secret123"
        })
        assert resp.status_code == 422

    def test_login_success(self, client):
        client.post("/api/v1/auth/register", json={
            "name": "Login", "email": "login@example.com", "password": "secret123"
        })
        resp = client.post("/api/v1/auth/login", json={
            "email": "login@example.com", "password": "secret123"
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data
        assert data["user"]["email"] == "login@example.com"

    def test_login_wrong_password(self, client):
        client.post("/api/v1/auth/register", json={
            "name": "Login", "email": "login2@example.com", "password": "secret123"
        })
        resp = client.post("/api/v1/auth/login", json={
            "email": "login2@example.com", "password": "wrongpass"
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com", "password": "secret123"
        })
        assert resp.status_code == 401

    def test_unauthorized_access(self, client):
        resp = client.get("/api/v1/users/me")
        assert resp.status_code == 401

    def test_get_me(self, client, auth_header):
        resp = client.get("/api/v1/users/me", headers=auth_header)
        assert resp.status_code == 200
        assert resp.get_json()["user"]["email"] == "authtest@example.com"

    def test_update_me(self, client, auth_header):
        resp = client.patch("/api/v1/users/me", headers=auth_header, json={
            "name": "UpdatedName"
        })
        assert resp.status_code == 200
        assert resp.get_json()["user"]["name"] == "UpdatedName"


class TestAdminAccess:
    def test_admin_can_list_users(self, client, admin_header):
        resp = client.get("/api/v1/users", headers=admin_header)
        assert resp.status_code == 200
        assert "pagination" in resp.get_json()

    def test_non_admin_cannot_list_users(self, client, auth_header):
        resp = client.get("/api/v1/users", headers=auth_header)
        assert resp.status_code == 403

    def test_admin_can_delete_user(self, client, admin_header, auth_header):
        resp = client.post("/api/v1/auth/register", json={
            "name": "ToDelete", "email": "del@example.com", "password": "secret123"
        })
        user_id = resp.get_json()["user"]["id"]
        resp = client.delete(f"/api/v1/users/{user_id}", headers=admin_header)
        assert resp.status_code == 200

    def test_admin_get_single_user(self, client, admin_header):
        resp = client.get("/api/v1/users/1", headers=admin_header)
        assert resp.status_code in (200, 404)
