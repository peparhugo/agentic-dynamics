class TestRateLimiting:
    def test_login_rate_limited(self, client):
        """auth/login is limited to 10/minute; the 11th attempt must get 429."""
        statuses = []
        for _ in range(11):
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "ghost@example.com", "password": "wrongpass1"},
            )
            statuses.append(resp.status_code)
        assert statuses[:10] == [401] * 10
        assert statuses[10] == 429
        body = resp.get_json()
        assert body["error"]["code"] == "rate_limit_exceeded"

    def test_rate_limit_headers_present(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@example.com", "password": "wrongpass1"},
        )
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers
