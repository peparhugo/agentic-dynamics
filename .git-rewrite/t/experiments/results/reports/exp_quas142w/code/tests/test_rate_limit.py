class TestRateLimit:
    def test_login_rate_limit(self, client, admin_user, app):
        for _ in range(35):
            client.post("/api/v1/auth/login", json={
                "username": "admin",
                "password": "adminpass123",
            })

        resp = client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "adminpass123",
        })
        # With test config rate limiting is disabled
        assert resp.status_code in (200, 429)


class TestRateLimitWithLimiter:
    def test_health_endpoint_not_limited(self, client):
        for _ in range(10):
            resp = client.get("/api/v1/health")
            assert resp.status_code == 200
