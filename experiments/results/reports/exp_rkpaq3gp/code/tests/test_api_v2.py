class TestItemsV2:
    def test_list_items_includes_version(self, client, auth_headers):
        resp = client.get("/api/v2/items", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["version"] == "v2"

    def test_create_item_includes_version(self, client, auth_headers):
        resp = client.post("/api/v2/items", headers=auth_headers, json={
            "name": "V2 Widget",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["item"]["version"] == "v2"

    def test_get_item_includes_version(self, client, auth_headers):
        create_resp = client.post("/api/v2/items", headers=auth_headers, json={
            "name": "V2 Item",
        })
        item_id = create_resp.get_json()["item"]["id"]

        resp = client.get(f"/api/v2/items/{item_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["item"]["version"] == "v2"

    def test_update_item_includes_version(self, client, auth_headers):
        create_resp = client.post("/api/v2/items", headers=auth_headers, json={
            "name": "V2 Old",
        })
        item_id = create_resp.get_json()["item"]["id"]

        resp = client.put(f"/api/v2/items/{item_id}", headers=auth_headers, json={
            "name": "V2 New",
        })
        assert resp.status_code == 200
        assert resp.get_json()["item"]["version"] == "v2"

    def test_v1_does_not_leak_version(self, client, auth_headers):
        create_resp = client.post("/api/v1/items", headers=auth_headers, json={
            "name": "V1 No Version",
        })
        item_id = create_resp.get_json()["item"]["id"]

        resp = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
        assert "version" not in resp.get_json()["item"]
