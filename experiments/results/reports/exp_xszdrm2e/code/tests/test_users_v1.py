class TestUsersV1:
    def test_list_users_empty(self, client, auth_headers):
        resp = client.get("/api/v1/users", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["pagination"]["total"] > 0

    def test_list_users_requires_auth(self, client):
        resp = client.get("/api/v1/users")
        assert resp.status_code == 401

    def test_get_user(self, client, auth_headers):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "getme@example.com", "password": "password123", "name": "Get Me"},
        )
        user_id = resp.get_json()["user"]["id"]

        resp2 = client.get(f"/api/v1/users/{user_id}", headers=auth_headers)
        assert resp2.status_code == 200
        assert resp2.get_json()["data"]["email"] == "getme@example.com"

    def test_get_user_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/users/nonexistent-id", headers=auth_headers)
        assert resp.status_code == 404

    def test_create_user(self, client, auth_headers):
        resp = client.post(
            "/api/v1/users",
            json={"email": "created@example.com", "password": "password123", "name": "Created"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.get_json()["data"]["email"] == "created@example.com"

    def test_create_user_duplicate(self, client, auth_headers):
        client.post(
            "/api/v1/users",
            json={"email": "dupv1@example.com", "password": "password123", "name": "Dup1"},
            headers=auth_headers,
        )
        resp = client.post(
            "/api/v1/users",
            json={"email": "dupv1@example.com", "password": "password123", "name": "Dup2"},
            headers=auth_headers,
        )
        assert resp.status_code == 409

    def test_update_user(self, client, auth_headers):
        resp = client.post(
            "/api/v1/users",
            json={"email": "update@example.com", "password": "password123", "name": "Old"},
            headers=auth_headers,
        )
        user_id = resp.get_json()["data"]["id"]

        resp2 = client.patch(
            f"/api/v1/users/{user_id}",
            json={"name": "Updated"},
            headers=auth_headers,
        )
        assert resp2.status_code == 200
        assert resp2.get_json()["data"]["name"] == "Updated"

    def test_delete_user(self, client, auth_headers):
        resp = client.post(
            "/api/v1/users",
            json={"email": "delete@example.com", "password": "password123", "name": "Delete"},
            headers=auth_headers,
        )
        user_id = resp.get_json()["data"]["id"]

        resp2 = client.delete(f"/api/v1/users/{user_id}", headers=auth_headers)
        assert resp2.status_code == 200
        assert resp2.get_json()["data"]["deleted"] is True

        resp3 = client.get(f"/api/v1/users/{user_id}", headers=auth_headers)
        assert resp3.status_code == 404

    def test_pagination(self, client, auth_headers):
        for i in range(5):
            client.post(
                "/api/v1/users",
                json={
                    "email": f"page{i}@example.com",
                    "password": "password123",
                    "name": f"Page {i}",
                },
                headers=auth_headers,
            )

        resp = client.get("/api/v1/users?page=1&per_page=2", headers=auth_headers)
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data["data"]) <= 2
        assert data["pagination"]["per_page"] == 2
        assert "has_next" in data["pagination"]
        assert "has_prev" in data["pagination"]
        assert "total_pages" in data["pagination"]
