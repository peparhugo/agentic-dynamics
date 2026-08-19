import json

import pytest

from shortener import create_app
from shortener.ratelimit import RateLimiter


class TestRateLimiterUnit:
    def test_allows_up_to_max_requests(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        results = [limiter.allow("client-a")[0] for _ in range(3)]
        assert results == [True, True, True]

    def test_blocks_after_max_requests(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            limiter.allow("client-a")
        allowed, retry_after = limiter.allow("client-a")
        assert allowed is False
        assert retry_after > 0

    def test_clients_are_isolated(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert limiter.allow("client-a")[0] is True
        assert limiter.allow("client-b")[0] is True
        assert limiter.allow("client-a")[0] is False

    def test_window_expiry_allows_new_requests(self):
        limiter = RateLimiter(max_requests=1, window_seconds=0.05)
        assert limiter.allow("client-a")[0] is True
        assert limiter.allow("client-a")[0] is False
        import time

        time.sleep(0.06)
        assert limiter.allow("client-a")[0] is True


@pytest.fixture
def limited_client(tmp_path):
    db_path = str(tmp_path / "rl.db")
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": db_path,
            "RATE_LIMIT_MAX": 3,
            "RATE_LIMIT_WINDOW": 60,
        }
    )
    client = app.test_client()
    yield client
    app.storage.close()


class TestRateLimitIntegration:
    def test_exceeding_limit_returns_429(self, limited_client):
        payload = json.dumps({"url": "https://example.com"})
        for _ in range(3):
            resp = limited_client.post("/api/shorten", data=payload, content_type="application/json")
            assert resp.status_code == 201

        resp = limited_client.post("/api/shorten", data=payload, content_type="application/json")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        assert "retry_after" in resp.get_json()

    def test_health_endpoint_not_rate_limited(self, limited_client):
        payload = json.dumps({"url": "https://example.com"})
        for _ in range(3):
            limited_client.post("/api/shorten", data=payload, content_type="application/json")

        for _ in range(10):
            resp = limited_client.get("/api/health")
            assert resp.status_code == 200
