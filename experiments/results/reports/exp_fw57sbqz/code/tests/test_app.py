import pytest


def _post(client, url, **kwargs):
    return client.post(
        "/api/shorten",
        json={"url": url, **kwargs},
        content_type="application/json",
    )


class TestShortenAPI:
    def test_shorten_returns_201_and_json(self, client):
        resp = _post(client, "https://example.com")
        assert resp.status_code == 201
        data = resp.get_json()
        assert "short_code" in data
        assert "short_url" in data
        assert data["original_url"] == "https://example.com"
        assert "expires_at" in data

    def test_shorten_code_is_alphanumeric(self, client):
        resp = _post(client, "https://example.com")
        code = resp.get_json()["short_code"]
        assert len(code) == 6
        assert code.isalnum()

    def test_shorten_missing_url(self, client):
        resp = client.post("/api/shorten", json={}, content_type="application/json")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_shorten_with_custom_code(self, client):
        resp = _post(client, "https://custom.example", custom_code="mycode")
        assert resp.status_code == 201
        assert resp.get_json()["short_code"] == "mycode"

    def test_shorten_custom_code_conflict(self, client):
        _post(client, "https://first.example", custom_code="taken")
        resp = _post(client, "https://second.example", custom_code="taken")
        assert resp.status_code == 409

    def test_shorten_different_urls_different_codes(self, client):
        codes = set()
        for i in range(10):
            resp = _post(client, f"https://example.com/{i}")
            codes.add(resp.get_json()["short_code"])
        assert len(codes) == 10

    def test_shorten_preserves_url(self, client):
        url = "https://example.com/path?q=1&r=2"
        resp = _post(client, url)
        assert resp.get_json()["original_url"] == url

    def test_shorten_with_ttl(self, client):
        resp = client.post(
            "/api/shorten?ttl_days=7",
            json={"url": "https://ephemeral.example"},
            content_type="application/json",
        )
        assert resp.status_code == 201


class TestRedirectAPI:
    def test_redirect_existing_url(self, client, sample_url):
        resp = client.get(f"/{sample_url}", follow_redirects=False)
        assert resp.status_code == 302
        assert "example.com/test" in resp.headers["Location"]

    def test_redirect_not_found(self, client):
        resp = client.get("/nonexist")
        assert resp.status_code == 404

    def test_redirect_increments_counter(self, client, sample_url):
        for _ in range(3):
            client.get(f"/{sample_url}", follow_redirects=False)
        stats = client.get(f"/api/stats/{sample_url}")
        assert stats.get_json()["access_count"] == 3


class TestStatsAPI:
    def test_stats_existing(self, client, sample_url):
        resp = client.get(f"/api/stats/{sample_url}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["short_code"] == sample_url
        assert data["access_count"] == 0

    def test_stats_not_found(self, client):
        resp = client.get("/api/stats/ghost")
        assert resp.status_code == 404


class TestHealthAPI:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"


class TestRateLimitInfo:
    def test_rate_limit_info(self, client):
        resp = client.get("/api/rate_limit")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "global_remaining" in data
        assert "create_remaining" in data
