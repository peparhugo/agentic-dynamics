class TestUsersV2:
    def test_list_users_includes_profile(self, client, auth_headers):
        resp = client.get("/api/v2/users", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        for user in data["data"]:
            assert "profile" in user
            assert "full_name" in user["profile"]
            assert "permissions" in user["profile"]
            assert "id" in user
            assert "email" in user

    def test_get_user_v2_includes_permissions(self, client, auth_headers):
        resp = client.post(
            "/api/v2/users",
            json={"email": "v2user@example.com", "password": "password123", "name": "V2 User"},
            headers=auth_headers,
        )
        user_id = resp.get_json()["data"]["id"]

        resp2 = client.get(f"/api/v2/users/{user_id}", headers=auth_headers)
        assert resp2.status_code == 200
        user_data = resp2.get_json()["data"]
        assert user_data["profile"]["permissions"] == ["read:own"]
        assert user_data["profile"]["full_name"] == "V2 User"

    def test_admin_has_elevated_permissions(self, client, admin_headers):
        resp = client.post(
            "/api/v2/users",
            json={
                "email": "admin_v2@example.com",
                "password": "password123",
                "name": "Admin V2",
                "role": "admin",
            },
            headers=admin_headers,
        )
        user_id = resp.get_json()["data"]["id"]

        resp2 = client.get(f"/api/v2/users/{user_id}", headers=admin_headers)
        perms = resp2.get_json()["data"]["profile"]["permissions"]
        assert "read:all" in perms
        assert "write:all" in perms

    def test_create_user_v2(self, client, auth_headers):
        resp = client.post(
            "/api/v2/users",
            json={"email": "v2create@example.com", "password": "password123", "name": "V2 Create"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.get_json()["data"]
        assert "profile" in data

    def test_update_user_v2_with_email(self, client, auth_headers):
        resp = client.post(
            "/api/v2/users",
            json={"email": "v2update@example.com", "password": "password123", "name": "Old"},
            headers=auth_headers,
        )
        user_id = resp.get_json()["data"]["id"]

        resp2 = client.patch(
            f"/api/v2/users/{user_id}",
            json={"email": "v2updated@example.com", "name": "New Name"},
            headers=auth_headers,
        )
        assert resp2.status_code == 200
        assert resp2.get_json()["data"]["email"] == "v2updated@example.com"
        assert resp2.get_json()["data"]["name"] == "New Name"

    def test_delete_user_v2(self, client, auth_headers):
        resp = client.post(
            "/api/v2/users",
            json={"email": "v2delete@example.com", "password": "password123", "name": "Del"},
            headers=auth_headers,
        )
        user_id = resp.get_json()["data"]["id"]

        resp2 = client.delete(f"/api/v2/users/{user_id}", headers=auth_headers)
        assert resp2.status_code == 200

    def test_v2_requires_auth(self, client):
        resp = client.get("/api/v2/users")
        assert resp.status_code == 401

    def test_v2_pagination(self, client, auth_headers):
        for i in range(3):
            client.post(
                "/api/v2/users",
                json={
                    "email": f"v2page{i}@example.com",
                    "password": "password123",
                    "name": f"V2 Page {i}",
                },
                headers=auth_headers,
            )

        resp = client.get("/api/v2/users?page=1&per_page=2&order=asc", headers=auth_headers)
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data["data"]) <= 2
        assert data["pagination"]["per_page"] == 2
