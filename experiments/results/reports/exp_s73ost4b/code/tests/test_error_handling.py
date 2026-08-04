class TestErrorHandling:
    def test_404_not_found(self, client):
        resp = client.get("/api/v1/nonexistent")
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_405_method_not_allowed(self, client):
        resp = client.patch("/api/v1/auth/login")
        assert resp.status_code in (405, 404)

    def test_widget_not_found(self, client, auth_header):
        resp = client.get("/api/v1/widgets/99999", headers=auth_header)
        assert resp.status_code == 404
        assert "not found" in resp.get_json()["error"].lower()

    def test_forbidden_widget_delete(self, client, auth_header):
        resp = client.post("/api/v1/widgets", headers=auth_header, json={
            "name": "Owner 1"
        })
        widget_id = resp.get_json()["widget"]["id"]

        resp2 = client.post("/api/v1/auth/register", json={
            "name": "User2", "email": "user2@example.com", "password": "secret123"
        })
        token2 = resp2.get_json()["token"]
        h2 = {"Authorization": f"Bearer {token2}"}

        resp3 = client.delete(f"/api/v1/widgets/{widget_id}", headers=h2)
        assert resp3.status_code == 403
