class TestItemsV1:
    def test_list_items_empty(self, client, auth_headers):
        resp = client.get("/api/v1/items", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["items"] == []
        assert data["meta"]["total"] == 0

    def test_create_item(self, client, auth_headers):
        resp = client.post("/api/v1/items", headers=auth_headers, json={
            "name": "Widget",
            "description": "A useful widget",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["item"]["name"] == "Widget"
        assert data["item"]["description"] == "A useful widget"

    def test_create_item_invalid(self, client, auth_headers):
        resp = client.post("/api/v1/items", headers=auth_headers, json={
            "description": "Missing name",
        })
        assert resp.status_code == 422

    def test_create_item_blank_name(self, client, auth_headers):
        resp = client.post("/api/v1/items", headers=auth_headers, json={
            "name": "   ",
        })
        assert resp.status_code == 422

    def test_get_item(self, client, auth_headers):
        create_resp = client.post("/api/v1/items", headers=auth_headers, json={
            "name": "Foo",
        })
        item_id = create_resp.get_json()["item"]["id"]

        resp = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["item"]["name"] == "Foo"

    def test_get_item_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/items/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_update_item(self, client, auth_headers):
        create_resp = client.post("/api/v1/items", headers=auth_headers, json={
            "name": "Old",
        })
        item_id = create_resp.get_json()["item"]["id"]

        resp = client.put(f"/api/v1/items/{item_id}", headers=auth_headers, json={
            "name": "New",
        })
        assert resp.status_code == 200
        assert resp.get_json()["item"]["name"] == "New"

    def test_update_item_forbidden(self, client, auth_headers):
        client.post("/auth/register", json={
            "username": "other",
            "email": "other@example.com",
            "password": "password123",
        })
        other_login = client.post("/auth/login", json={
            "username": "other",
            "password": "password123",
        })
        other_headers = {"Authorization": f"Bearer {other_login.get_json()['access_token']}"}

        create_resp = client.post("/api/v1/items", headers=auth_headers, json={
            "name": "Mine",
        })
        item_id = create_resp.get_json()["item"]["id"]

        resp = client.put(f"/api/v1/items/{item_id}", headers=other_headers, json={
            "name": "Hijack",
        })
        assert resp.status_code == 403

    def test_delete_item(self, client, auth_headers):
        create_resp = client.post("/api/v1/items", headers=auth_headers, json={
            "name": "ToDelete",
        })
        item_id = create_resp.get_json()["item"]["id"]

        resp = client.delete(f"/api/v1/items/{item_id}", headers=auth_headers)
        assert resp.status_code == 200

        resp2 = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
        assert resp2.status_code == 404

    def test_pagination(self, client, auth_headers):
        for i in range(5):
            client.post("/api/v1/items", headers=auth_headers, json={
                "name": f"Item {i}",
            })

        resp = client.get("/api/v1/items?page=1&per_page=2", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["items"]) == 2
        assert data["meta"]["page"] == 1
        assert data["meta"]["per_page"] == 2
        assert data["meta"]["total"] == 5
        assert data["meta"]["has_next"] is True

    def test_pagination_invalid_params(self, client, auth_headers):
        resp = client.get("/api/v1/items?page=0&per_page=0", headers=auth_headers)
        assert resp.status_code == 422

    def test_unauthenticated(self, client):
        resp = client.get("/api/v1/items")
        assert resp.status_code == 401
