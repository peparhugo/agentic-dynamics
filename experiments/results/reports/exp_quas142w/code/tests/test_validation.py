class TestValidation:
    def test_create_user_invalid_username_short(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.post("/api/v1/users", json={
            "username": "ab",
            "email": "valid@example.com",
            "password": "validpass123",
        }, headers=headers)
        assert resp.status_code == 422
        data = resp.get_json()
        assert "username" in data.get("messages", {})

    def test_create_user_invalid_email(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.post("/api/v1/users", json={
            "username": "validuser",
            "email": "not-an-email",
            "password": "validpass123",
        }, headers=headers)
        assert resp.status_code == 422

    def test_create_user_short_password(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.post("/api/v1/users", json={
            "username": "validuser",
            "email": "valid@example.com",
            "password": "short",
        }, headers=headers)
        assert resp.status_code == 422
        data = resp.get_json()
        assert "password" in data.get("messages", {})

    def test_create_user_invalid_username_chars(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.post("/api/v1/users", json={
            "username": "user name!",
            "email": "valid@example.com",
            "password": "validpass123",
        }, headers=headers)
        assert resp.status_code == 422

    def test_create_user_duplicate_username(self, client, admin_token, normal_user):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.post("/api/v1/users", json={
            "username": "testuser",
            "email": "another@example.com",
            "password": "validpass123",
        }, headers=headers)
        assert resp.status_code == 409

    def test_create_user_duplicate_email(self, client, admin_token, normal_user):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.post("/api/v1/users", json={
            "username": "another",
            "email": "test@example.com",
            "password": "validpass123",
        }, headers=headers)
        assert resp.status_code == 409

    def test_update_user_bad_email(self, client, admin_token, normal_user):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.put(f"/api/v1/users/{normal_user.id}", json={
            "email": "invalid",
        }, headers=headers)
        assert resp.status_code == 422

    def test_update_user_not_found(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.put("/api/v1/users/99999", json={"username": "newname"}, headers=headers)
        assert resp.status_code == 404
