"""Unit tests for the sliding-window limiter, plus API integration."""

from shortener import create_app
from shortener.ratelimit import SlidingWindowLimiter


class TestLimiterUnit:
    def test_allows_up_to_max(self):
        lim = SlidingWindowLimiter(max_requests=3, window_seconds=10)
        assert all(lim.check("k", now=t)[0] for t in (0.0, 1.0, 2.0))

    def test_blocks_over_max_with_retry_after(self):
        lim = SlidingWindowLimiter(max_requests=3, window_seconds=10)
        for t in (0.0, 1.0, 2.0):
            lim.check("k", now=t)
        allowed, retry_after = lim.check("k", now=3.0)
        assert not allowed
        assert retry_after == 7.0  # oldest hit (t=0) expires at t=10

    def test_window_slides(self):
        lim = SlidingWindowLimiter(max_requests=2, window_seconds=10)
        lim.check("k", now=0.0)
        lim.check("k", now=1.0)
        assert not lim.check("k", now=5.0)[0]
        assert lim.check("k", now=10.5)[0]  # t=0 hit expired

    def test_keys_are_independent(self):
        lim = SlidingWindowLimiter(max_requests=1, window_seconds=10)
        assert lim.check("a", now=0.0)[0]
        assert lim.check("b", now=0.0)[0]
        assert not lim.check("a", now=1.0)[0]

    def test_reset(self):
        lim = SlidingWindowLimiter(max_requests=1, window_seconds=10)
        lim.check("k", now=0.0)
        lim.reset("k")
        assert lim.check("k", now=0.1)[0]


class TestLimiterIntegration:
    def test_api_returns_429_with_retry_after(self, tmp_path):
        app = create_app({
            "TESTING": True,
            "DATABASE": str(tmp_path / "rl.db"),
            "RATE_LIMIT_MAX": 5,
            "RATE_LIMIT_WINDOW": 60.0,
        })
        client = app.test_client()

        for _ in range(5):
            assert client.get("/health").status_code == 200

        resp = client.get("/health")
        assert resp.status_code == 429
        assert resp.get_json()["error"] == "rate limit exceeded"
        assert int(resp.headers["Retry-After"]) >= 1

    def test_limit_is_per_client(self, tmp_path):
        app = create_app({
            "TESTING": True,
            "DATABASE": str(tmp_path / "rl2.db"),
            "RATE_LIMIT_MAX": 2,
            "RATE_LIMIT_WINDOW": 60.0,
        })
        client = app.test_client()

        h1 = {"X-Forwarded-For": "10.0.0.1"}
        h2 = {"X-Forwarded-For": "10.0.0.2"}
        client.get("/health", headers=h1)
        client.get("/health", headers=h1)
        assert client.get("/health", headers=h1).status_code == 429
        assert client.get("/health", headers=h2).status_code == 200
