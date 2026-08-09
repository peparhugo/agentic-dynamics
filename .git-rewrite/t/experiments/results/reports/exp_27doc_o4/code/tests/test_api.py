"""End-to-end API tests using the Flask test client."""

LONG_URL = "https://example.com/some/very/long/path?with=params"


def shorten(client, url=LONG_URL, **kwargs):
    payload = {"url": url, **kwargs}
    return client.post("/api/shorten", json=payload)


class TestShorten:
    def test_creates_short_url(self, client):
        resp = shorten(client)
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["long_url"] == LONG_URL
        assert len(body["code"]) == 6
        assert body["short_url"].endswith("/" + body["code"])
        assert body["clicks"] == 0

    def test_idempotent_for_same_url(self, client):
        first = shorten(client).get_json()
        resp = shorten(client)
        assert resp.status_code == 200
        assert resp.get_json()["code"] == first["code"]

    def test_custom_code(self, client):
        resp = shorten(client, custom_code="my-link")
        assert resp.status_code == 201
        assert resp.get_json()["code"] == "my-link"

    def test_custom_code_conflict(self, client):
        assert shorten(client, custom_code="taken1").status_code == 201
        resp = shorten(client, url="https://example.org/", custom_code="taken1")
        assert resp.status_code == 409

    def test_invalid_custom_codes(self, client):
        for bad in ["ab", "has space", "x" * 33, "semi;colon"]:
            resp = shorten(client, custom_code=bad)
            assert resp.status_code == 400, bad

    def test_rejects_invalid_urls(self, client):
        for bad in ["", "notaurl", "ftp://example.com/x", "javascript:alert(1)",
                    "http://", "https://" + "a" * 2050]:
            resp = shorten(client, url=bad)
            assert resp.status_code == 400, bad

    def test_rejects_non_json_body(self, client):
        resp = client.post("/api/shorten", data="url=x",
                           content_type="application/x-www-form-urlencoded")
        assert resp.status_code == 400


class TestRedirect:
    def test_redirects_and_counts_clicks(self, client):
        code = shorten(client).get_json()["code"]

        resp = client.get(f"/{code}")
        assert resp.status_code == 302
        assert resp.headers["Location"] == LONG_URL

        client.get(f"/{code}")
        stats = client.get(f"/api/urls/{code}").get_json()
        assert stats["clicks"] == 2

    def test_unknown_code_404(self, client):
        assert client.get("/nope42").status_code == 404


class TestStatsAndDelete:
    def test_stats(self, client):
        code = shorten(client).get_json()["code"]
        resp = client.get(f"/api/urls/{code}")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["long_url"] == LONG_URL
        assert "created_at" in body

    def test_stats_unknown_404(self, client):
        assert client.get("/api/urls/missing").status_code == 404

    def test_delete(self, client):
        code = shorten(client).get_json()["code"]
        assert client.delete(f"/api/urls/{code}").status_code == 204
        assert client.get(f"/{code}").status_code == 404
        assert client.delete(f"/api/urls/{code}").status_code == 404


class TestRateLimit:
    def test_limit_enforced_and_recovers(self, tmp_path):
        from shortener import create_app

        app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(tmp_path / "rl.db"),
                "RATE_LIMIT_REQUESTS": 3,
                "RATE_LIMIT_WINDOW": 60,
            }
        )
        client = app.test_client()

        for _ in range(3):
            assert client.get("/api/health").status_code == 200

        resp = client.get("/api/health")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        assert resp.get_json()["error"] == "rate limit exceeded"

        # Redirect path is not rate-limited.
        assert client.get("/nope42").status_code == 404

        # Window expiry restores access.
        app.extensions["rate_limiter"].reset()
        assert client.get("/api/health").status_code == 200

    def test_limits_are_per_client(self, tmp_path):
        from shortener import create_app

        app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(tmp_path / "rl2.db"),
                "RATE_LIMIT_REQUESTS": 1,
                "RATE_LIMIT_WINDOW": 60,
            }
        )
        client = app.test_client()

        assert client.get("/api/health",
                          headers={"X-Forwarded-For": "10.0.0.1"}).status_code == 200
        assert client.get("/api/health",
                          headers={"X-Forwarded-For": "10.0.0.1"}).status_code == 429
        # Different client, independent bucket.
        assert client.get("/api/health",
                          headers={"X-Forwarded-For": "10.0.0.2"}).status_code == 200
