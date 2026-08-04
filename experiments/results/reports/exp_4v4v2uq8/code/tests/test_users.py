import pytest


class TestUsersV1:
    def test_create_user(self, client):
        resp = client.post(
            "/api/v1/users",
            json={"username": "newuser", "email": "new@example.com", "password": "secret123"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["username"] == "newuser"
        assert data["email"] == "new@example.com"
        assert data["role"] == "user"
        assert "password_hash" not in data

    def test_create_user_missing_fields(self, client):
        resp = client.post("/api/v1/users", json={"username": "x"})
        assert resp.status_code == 422

    def test_create_user_short_password(self, client):
        resp = client.post(
            "/api/v1/users",
            json={"username": "xuser", "email": "x@test.com", "password": "ab"},
        )
        assert resp.status_code == 422

    def test_create_user_invalid_email(self, client):
        resp = client.post(
            "/api/v1/users",
            json={"username": "xuser", "email": "notanemail", "password": "secret123"},
        )
        assert resp.status_code == 422

    def test_create_user_duplicate_username(self, client, sample_user):
        resp = client.post(
            "/api/v1/users",
            json={"username": "testuser", "email": "other@example.com", "password": "secret123"},
        )
        assert resp.status_code == 409
        assert resp.get_json()["code"] == "USERNAME_TAKEN"

    def test_create_user_duplicate_email(self, client, sample_user):
        resp = client.post(
            "/api/v1/users",
            json={"username": "otheruser", "email": "test@example.com", "password": "secret123"},
        )
        assert resp.status_code == 409
        assert resp.get_json()["code"] == "EMAIL_TAKEN"

    def test_list_users(self, client, sample_user):
        resp = client.get("/api/v1/users")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "data" in data
        assert "pagination" in data
        assert len(data["data"]) >= 1

    def test_get_user(self, client, sample_user):
        resp = client.get(f"/api/v1/users/{sample_user['id']}")
        assert resp.status_code == 200
        assert resp.get_json()["username"] == "testuser"

    def test_get_user_not_found(self, client):
        resp = client.get("/api/v1/users/nonexistent")
        assert resp.status_code == 404

    def test_update_own_profile(self, client, sample_user, auth_headers):
        resp = client.put(
            f"/api/v1/users/{sample_user['id']}",
            json={"email": "updated@example.com"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["email"] == "updated@example.com"

    def test_update_other_as_non_admin(self, client, sample_user, auth_headers):
        other = client.post(
            "/api/v1/users",
            json={"username": "other", "email": "other@test.com", "password": "secret123"},
        ).get_json()

        resp = client.put(
            f"/api/v1/users/{other['id']}",
            json={"email": "hacked@example.com"},
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_update_other_as_admin(self, client, admin_headers):
        other = client.post(
            "/api/v1/users",
            json={"username": "other", "email": "other@test.com", "password": "secret123"},
        ).get_json()

        resp = client.put(
            f"/api/v1/users/{other['id']}",
            json={"email": "adminchanged@example.com"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.get_json()["email"] == "adminchanged@example.com"

    def test_update_no_fields(self, client, sample_user, auth_headers):
        resp = client.put(
            f"/api/v1/users/{sample_user['id']}",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_delete_own_account(self, client, auth_headers):
        sample_user = client.post(
            "/api/v1/users",
            json={"username": "todelete", "email": "del@test.com", "password": "secret123"},
        ).get_json()

        token = client.post(
            "/api/v1/auth/login",
            json={"username": "todelete", "password": "secret123"},
        ).get_json()["access_token"]

        resp = client.delete(
            f"/api/v1/users/{sample_user['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_delete_other_as_non_admin(self, client, sample_user, auth_headers):
        other = client.post(
            "/api/v1/users",
            json={"username": "other2", "email": "other2@test.com", "password": "secret123"},
        ).get_json()

        resp = client.delete(
            f"/api/v1/users/{other['id']}",
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_delete_as_admin(self, client, admin_headers):
        other = client.post(
            "/api/v1/users",
            json={"username": "other3", "email": "other3@test.com", "password": "secret123"},
        ).get_json()

        resp = client.delete(
            f"/api/v1/users/{other['id']}",
            headers=admin_headers,
        )
        assert resp.status_code == 200

    def test_delete_not_found(self, client, auth_headers):
        resp = client.delete("/api/v1/users/nonexistent", headers=auth_headers)
        assert resp.status_code == 404

    def test_protected_endpoint_no_auth(self, client, sample_user):
        resp = client.delete(f"/api/v1/users/{sample_user['id']}")
        assert resp.status_code == 401

    def test_protected_endpoint_invalid_token(self, client, sample_user):
        resp = client.delete(
            f"/api/v1/users/{sample_user['id']}",
            headers={"Authorization": "Bearer invalidtoken"},
        )
        assert resp.status_code == 401

    def test_update_username_conflict(self, client, auth_headers):
        client.post(
            "/api/v1/users",
            json={"username": "bob", "email": "bob@test.com", "password": "secret123"},
        )
        alice = client.post(
            "/api/v1/users",
            json={"username": "alice", "email": "alice@test.com", "password": "secret123"},
        ).get_json()

        alice_token = client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "secret123"},
        ).get_json()["access_token"]

        resp = client.put(
            f"/api/v1/users/{alice['id']}",
            json={"username": "bob"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert resp.status_code == 409

    def test_update_email_conflict(self, client, auth_headers):
        client.post(
            "/api/v1/users",
            json={"username": "bob", "email": "bob@test.com", "password": "secret123"},
        )
        alice = client.post(
            "/api/v1/users",
            json={"username": "alice", "email": "alice@test.com", "password": "secret123"},
        ).get_json()

        alice_token = client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "secret123"},
        ).get_json()["access_token"]

        resp = client.put(
            f"/api/v1/users/{alice['id']}",
            json={"email": "bob@test.com"},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert resp.status_code == 409
