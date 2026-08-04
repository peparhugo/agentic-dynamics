class TestErrorHandling:
    def test_404_not_found(self, client):
        resp = client.get("/api/v1/nonexistent")
        assert resp.status_code == 404

    def test_405_method_not_allowed(self, client):
        resp = client.patch("/health")
        assert resp.status_code == 405

    def test_error_response_structure(self, client, auth_headers):
        resp = client.get("/api/v1/users/nonexistent", headers=auth_headers)
        data = resp.get_json()
        assert "error" in data
