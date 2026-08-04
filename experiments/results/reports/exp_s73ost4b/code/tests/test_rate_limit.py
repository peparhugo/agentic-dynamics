import time
from app.middleware.rate_limit import _rate_window_starts


class TestRateLimit:
    def setup_method(self):
        _rate_window_starts.clear()

    def test_rate_limit_headers_present(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "email": "x@x.com", "password": "xxxxxx"
        })
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers
        assert "X-RateLimit-Reset" in resp.headers

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"
        assert "v1" in resp.get_json()["versions"]
        assert "v2" in resp.get_json()["versions"]

    def test_rate_limit_headers_on_protected(self, client, auth_header):
        resp = client.get("/api/v1/users/me", headers=auth_header)
        assert "X-RateLimit-Limit" in resp.headers
        assert int(resp.headers["X-RateLimit-Remaining"]) >= 0
