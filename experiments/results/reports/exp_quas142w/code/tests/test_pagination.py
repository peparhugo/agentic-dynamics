class TestPagination:
    def test_list_users_with_pagination_defaults(self, client, admin_token, normal_user):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.get("/api/v1/users", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "data" in data
        assert "pagination" in data
        p = data["pagination"]
        assert p["page"] == 1
        assert p["per_page"] == 20
        assert p["total"] >= 2
        assert p["pages"] >= 1

    def test_list_users_page_1(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.get("/api/v1/users?page=1&per_page=1", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 1
        assert len(data["data"]) == 1

    def test_list_users_page_out_of_range(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.get("/api/v1/users?page=999&per_page=10", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]) == 0

    def test_list_users_per_page_capped(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.get("/api/v1/users?per_page=200", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["pagination"]["per_page"] <= 100

    def test_list_users_pagination_metadata(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.get("/api/v1/users?page=1&per_page=1", headers=headers)
        data = resp.get_json()
        p = data["pagination"]
        assert "has_next" in p
        assert "has_prev" in p
        assert p["has_prev"] is False

    def test_v2_only_active_users(self, client, admin_token, normal_user):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.get("/api/v2/users", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        for user in data["data"]:
            assert user["is_active"] is True
