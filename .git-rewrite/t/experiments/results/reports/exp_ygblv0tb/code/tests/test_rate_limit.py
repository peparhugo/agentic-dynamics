class TestRateLimiting:
    def test_login_rate_limited(self, client):
        payload = {"email": "ghost@example.com", "password": "wrongwrong"}
        statuses = [client.post("/api/v1/auth/login", json=payload).status_code
                    for _ in range(11)]
        assert statuses[:10] == [401] * 10
        assert statuses[10] == 429

    def test_rate_limit_error_shape(self, client):
        payload = {"email": "ghost@example.com", "password": "wrongwrong"}
        for _ in range(10):
            client.post("/api/v1/auth/login", json=payload)
        resp = client.post("/api/v1/auth/login", json=payload)
        assert resp.status_code == 429
        body = resp.get_json()
        assert body["error"]["code"] == "rate_limited"
        assert body["error"]["status"] == 429

    def test_rate_limit_headers_present(self, client):
        resp = client.post("/api/v1/auth/login",
                           json={"email": "a@b.com", "password": "xxxxxxxx"})
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers

    def test_register_rate_limited(self, client):
        statuses = []
        for i in range(11):
            resp = client.post(
                "/api/v1/auth/register",
                json={"email": f"user{i}@example.com", "password": "longenough"})
            statuses.append(resp.status_code)
        assert statuses[:10] == [201] * 10
        assert statuses[10] == 429
