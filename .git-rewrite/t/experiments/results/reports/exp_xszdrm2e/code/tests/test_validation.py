class TestValidation:
    def test_user_create_invalid_email(self, client, auth_headers):
        resp = client.post(
            "/api/v1/users",
            json={"email": "bad-email", "password": "password123", "name": "Test"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_user_create_short_password(self, client, auth_headers):
        resp = client.post(
            "/api/v1/users",
            json={"email": "test@example.com", "password": "123", "name": "Test"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_user_create_missing_fields(self, client, auth_headers):
        resp = client.post("/api/v1/users", json={}, headers=auth_headers)
        assert resp.status_code == 422

    def test_user_update_invalid_role(self, client, auth_headers):
        resp = client.post(
            "/api/v1/users",
            json={"email": "role@example.com", "password": "password123", "name": "Role"},
            headers=auth_headers,
        )
        user_id = resp.get_json()["data"]["id"]

        resp2 = client.patch(
            f"/api/v1/users/{user_id}",
            json={"role": "superadmin"},
            headers=auth_headers,
        )
        assert resp2.status_code == 422
