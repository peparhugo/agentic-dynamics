import time

import pytest

from ratelimit import SlidingWindowRateLimiter


class TestRateLimiter:
    def test_allows_under_limit(self):
        rl = SlidingWindowRateLimiter(max_requests=5, window_seconds=10)
        for _ in range(5):
            assert rl.is_allowed("client1")

    def test_blocks_over_limit(self):
        rl = SlidingWindowRateLimiter(max_requests=3, window_seconds=10)
        for _ in range(3):
            assert rl.is_allowed("client1")
        assert not rl.is_allowed("client1")

    def test_remaining_counts_down(self):
        rl = SlidingWindowRateLimiter(max_requests=5, window_seconds=10)
        assert rl.remaining("client1") == 5
        rl.is_allowed("client1")
        assert rl.remaining("client1") == 4

    def test_different_keys_independent(self):
        rl = SlidingWindowRateLimiter(max_requests=3, window_seconds=10)
        for _ in range(3):
            rl.is_allowed("client1")
        assert not rl.is_allowed("client1")
        assert rl.is_allowed("client2")

    def test_sliding_window_decay(self, monkeypatch):
        rl = SlidingWindowRateLimiter(max_requests=3, window_seconds=1)
        for _ in range(3):
            assert rl.is_allowed("client1")
        assert not rl.is_allowed("client1")

        time.sleep(1.1)

        assert rl.is_allowed("client1")

    def test_reset_clears_key(self):
        rl = SlidingWindowRateLimiter(max_requests=3, window_seconds=10)
        for _ in range(3):
            rl.is_allowed("client1")
        assert not rl.is_allowed("client1")
        rl.reset("client1")
        assert rl.is_allowed("client1")

    def test_cleanup_removes_stale(self):
        rl = SlidingWindowRateLimiter(max_requests=10, window_seconds=10)
        rl.is_allowed("old_client")
        rl._buckets["old_client"] = [0.0]
        rl.cleanup(max_age_seconds=0)
        assert rl.remaining("old_client") == 10
        assert "old_client" not in rl._buckets

    def test_rate_limiter_rate_limit(self, client):
        import app as app_module

        app_module.create_limiter.reset("test_rl_client")

        from config import Config
        Config.CREATE_RATE_LIMIT_REQUESTS = 2
        Config.CREATE_RATE_LIMIT_WINDOW_SEC = 60
        app_module.create_limiter = SlidingWindowRateLimiter(
            max_requests=2, window_seconds=60
        )

        headers = {"X-Forwarded-For": "10.0.0.99"}
        for _ in range(2):
            resp = client.post(
                "/api/shorten",
                json={"url": "https://test.example"},
                content_type="application/json",
                headers=headers,
            )
            assert resp.status_code == 201

        resp = client.post(
            "/api/shorten",
            json={"url": "https://blocked.example"},
            content_type="application/json",
            headers=headers,
        )
        assert resp.status_code == 429
