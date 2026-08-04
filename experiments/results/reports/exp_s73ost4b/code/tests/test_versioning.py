class TestAPIVersioning:
    def test_v1_widget_create_response(self, client, auth_header):
        resp = client.post("/api/v1/widgets", headers=auth_header, json={
            "name": "V1 Widget"
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert "widget" in data
        assert "version" not in data

    def test_v2_widget_create_response(self, client, auth_header):
        resp = client.post("/api/v2/widgets", headers=auth_header, json={
            "name": "V2 Widget"
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert "widget" in data
        assert data["version"] == "v2"
        assert data["status"] == "created"

    def test_v2_list_widgets_has_version(self, client, auth_header):
        for i in range(3):
            client.post("/api/v2/widgets", headers=auth_header, json={
                "name": f"V2 Widget {i}"
            })
        resp = client.get("/api/v2/widgets", headers=auth_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["version"] == "v2"

    def test_v2_widget_not_found_has_version(self, client, auth_header):
        resp = client.get("/api/v2/widgets/99999", headers=auth_header)
        assert resp.status_code == 404
        assert resp.get_json().get("version") == "v2"

    def test_v2_forbidden_has_version(self, client, auth_header):
        resp = client.post("/api/v2/widgets", headers=auth_header, json={
            "name": "MyV2"
        })
        widget_id = resp.get_json()["widget"]["id"]

        resp2 = client.post("/api/v1/auth/register", json={
            "name": "U2", "email": "u2v2@example.com", "password": "secret123"
        })
        token2 = resp2.get_json()["token"]
        h2 = {"Authorization": f"Bearer {token2}"}

        resp3 = client.delete(f"/api/v2/widgets/{widget_id}", headers=h2)
        assert resp3.status_code == 403
        assert resp3.get_json().get("version") == "v2"

    def test_v2_admin_endpoint(self, client, admin_header):
        resp = client.get("/api/v2/widgets/admin/all", headers=admin_header)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["version"] == "v2"
        assert "note" in data

    def test_v2_admin_endpoint_rejects_non_admin(self, client, auth_header):
        resp = client.get("/api/v2/widgets/admin/all", headers=auth_header)
        assert resp.status_code == 403

    def test_v1_widget_put(self, client, auth_header):
        resp = client.post("/api/v1/widgets", headers=auth_header, json={
            "name": "Original"
        })
        widget_id = resp.get_json()["widget"]["id"]
        resp = client.put(f"/api/v1/widgets/{widget_id}", headers=auth_header, json={
            "name": "Updated via PUT"
        })
        assert resp.status_code == 200
        assert resp.get_json()["widget"]["name"] == "Updated via PUT"

    def test_v2_widget_patch(self, client, auth_header):
        resp = client.post("/api/v2/widgets", headers=auth_header, json={
            "name": "Original V2"
        })
        widget_id = resp.get_json()["widget"]["id"]
        resp = client.patch(f"/api/v2/widgets/{widget_id}", headers=auth_header, json={
            "name": "Updated via PATCH"
        })
        assert resp.status_code == 200
        assert resp.get_json()["widget"]["name"] == "Updated via PATCH"
        assert resp.get_json()["version"] == "v2"

    def test_v1_v2_independent(self, client, auth_header):
        r1 = client.post("/api/v1/widgets", headers=auth_header, json={"name": "V1"})
        r2 = client.post("/api/v2/widgets", headers=auth_header, json={"name": "V2"})
        assert r1.status_code == 201
        assert r2.status_code == 201

        list1 = client.get("/api/v1/widgets", headers=auth_header)
        list2 = client.get("/api/v2/widgets", headers=auth_header)
        assert list1.get_json()["pagination"]["total"] == 2
        assert list2.get_json()["pagination"]["total"] == 2
