class TestUserEndpoints:
    def test_get_me(self, client, auth_headers):
        resp = client.get("/api/users/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert "password_hash" not in data

    def test_get_me_unauthenticated(self, client):
        resp = client.get("/api/users/me")
        assert resp.status_code == 401

    def test_list_users(self, client, auth_headers):
        resp = client.get("/api/users", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]) >= 1
        assert data["pagination"]["total"] >= 1

    def test_get_user_by_id(self, client, auth_headers):
        list_resp = client.get("/api/users", headers=auth_headers)
        user = list_resp.get_json()["data"][0]
        resp = client.get(f"/api/users/{user['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["username"] == user["username"]

    def test_get_nonexistent_user(self, client, auth_headers):
        resp = client.get("/api/users/nope", headers=auth_headers)
        assert resp.status_code == 404

    def test_list_users_pagination(self, client, auth_headers, second_user_headers):
        resp = client.get("/api/users?page=1&per_page=1", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]) == 1
        assert data["pagination"]["per_page"] == 1
