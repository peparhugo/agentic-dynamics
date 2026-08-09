class TestUserCRUD:
    def test_list_users(self, client, auth_headers):
        resp = client.get("/v1/users", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "data" in data
        assert "pagination" in data
        assert len(data["data"]) >= 1
        assert data["pagination"]["page"] == 1
        assert "total" in data["pagination"]

    def test_list_users_pagination(self, client, auth_headers):
        for i in range(5):
            client.post("/v1/auth/register", json={
                "username": f"pageuser{i}", "email": f"page{i}@example.com", "password": "password123",
            })
        resp = client.get("/v1/users?page=1&per_page=2", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]) <= 2
        assert data["pagination"]["per_page"] == 2

    def test_list_users_per_page_max(self, client, auth_headers):
        resp = client.get("/v1/users?per_page=200", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["pagination"]["per_page"] == 100

    def test_list_users_negative_page(self, client, auth_headers):
        resp = client.get("/v1/users?page=-1", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["pagination"]["page"] == 1

    def test_list_users_invalid_params(self, client, auth_headers):
        resp = client.get("/v1/users?page=abc&per_page=xyz", headers=auth_headers)
        assert resp.status_code == 200

    def test_get_user(self, client, auth_headers):
        resp = client.get("/v1/users/1", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["id"] == 1

    def test_get_nonexistent_user(self, client, auth_headers):
        resp = client.get("/v1/users/9999", headers=auth_headers)
        assert resp.status_code == 404

    def test_update_user(self, client, auth_headers):
        resp = client.put("/v1/users/1", headers=auth_headers, json={
            "username": "updateduser"
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["username"] == "updateduser"

    def test_update_other_user_forbidden(self, client, auth_headers, auth_headers2):
        resp = client.put("/v1/users/1", headers=auth_headers2, json={
            "username": "hacked"
        })
        assert resp.status_code == 403

    def test_update_duplicate_username(self, client, auth_headers, auth_headers2):
        resp = client.put("/v1/users/1", headers=auth_headers, json={
            "username": "otheruser"
        })
        assert resp.status_code == 409

    def test_update_password(self, client, auth_headers):
        resp = client.put("/v1/users/1", headers=auth_headers, json={
            "password": "newpassword123"
        })
        assert resp.status_code == 200
        login_resp = client.post("/v1/auth/login", json={
            "email": "test@example.com", "password": "newpassword123",
        })
        assert login_resp.status_code == 200

    def test_delete_user(self, client, auth_headers):
        resp = client.post("/v1/auth/register", json={
            "username": "todelete", "email": "delete@example.com", "password": "password123",
        })
        login_resp = client.post("/v1/auth/login", json={
            "email": "delete@example.com", "password": "password123",
        })
        user_id = login_resp.get_json()["user"]["id"]
        headers = {"Authorization": f"Bearer {login_resp.get_json()['access_token']}"}

        resp = client.delete(f"/v1/users/{user_id}", headers=headers)
        assert resp.status_code == 200

    def test_delete_other_user_forbidden(self, client, auth_headers, auth_headers2):
        resp = client.delete("/v1/users/1", headers=auth_headers2)
        assert resp.status_code == 403

    def test_delete_nonexistent_user(self, client, auth_headers):
        resp = client.delete("/v1/users/9999", headers=auth_headers)
        assert resp.status_code == 404 if resp.status_code != 403 else 403
