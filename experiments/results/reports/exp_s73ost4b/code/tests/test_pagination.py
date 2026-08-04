class TestPagination:
    def test_widget_list_pagination_structure(self, client, auth_header):
        for i in range(5):
            client.post("/api/v1/widgets", headers=auth_header, json={
                "name": f"Widget {i}"
            })

        resp = client.get("/api/v1/widgets?page=1&per_page=3", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "data" in data
        assert "pagination" in data
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 3
        assert data["pagination"]["total"] == 5
        assert len(data["data"]) == 3
        assert data["pagination"]["has_next"] is True
        assert data["pagination"]["has_prev"] is False

    def test_pagination_page_2(self, client, auth_header):
        for i in range(5):
            client.post("/api/v1/widgets", headers=auth_header, json={
                "name": f"Widget {i}"
            })

        resp = client.get("/api/v1/widgets?page=2&per_page=3", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]) == 2
        assert data["pagination"]["has_next"] is False
        assert data["pagination"]["has_prev"] is True

    def test_pagination_defaults(self, client, auth_header):
        resp = client.get("/api/v1/widgets", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 20

    def test_pagination_empty(self, client, auth_header):
        resp = client.get("/api/v1/widgets", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"] == []
        assert data["pagination"]["total"] == 0

    def test_pagination_beyond_range(self, client, auth_header):
        for i in range(3):
            client.post("/api/v1/widgets", headers=auth_header, json={
                "name": f"Widget {i}"
            })
        resp = client.get("/api/v1/widgets?page=999", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"] == []
        assert data["pagination"]["total"] == 3
