class TestErrorHandling:
    def test_404_is_json(self, client):
        resp = client.get("/api/v1/does-not-exist")
        assert resp.status_code == 404
        assert resp.content_type.startswith("application/json")
        assert resp.get_json()["error"]["status"] == 404

    def test_405_is_json(self, client):
        resp = client.delete("/api/v1/auth/login")
        assert resp.status_code == 405
        assert resp.get_json()["error"]["status"] == 405

    def test_validation_error_lists_fields(self, client):
        resp = client.post("/api/v1/auth/register", json={})
        assert resp.status_code == 400
        details = resp.get_json()["error"]["details"]
        assert set(details) == {"email", "password"}

    def test_error_envelope_is_consistent(self, client):
        resp = client.get("/api/v1/auth/me")
        err = resp.get_json()["error"]
        assert set(err) >= {"code", "message", "status"}


class TestVersioning:
    def test_api_index_lists_versions(self, client):
        resp = client.get("/api")
        assert resp.status_code == 200
        versions = resp.get_json()["versions"]
        assert versions[0]["version"] == "v1"
        assert versions[0]["base_url"] == "/api/v1"

    def test_v1_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.get_json() == {"status": "ok", "version": "v1"}

    def test_unversioned_paths_do_not_exist(self, client):
        assert client.get("/api/notes").status_code == 404
        assert client.post("/auth/login", json={}).status_code == 404
