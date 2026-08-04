import pytest

from shortener.ratelimit import RateLimiter


class TestRateLimiter:
    def test_allows_up_to_limit(self):
        rl = RateLimiter(max_requests=3, window_seconds=60)
        assert all(rl.allow("k", now=i) for i in range(3))

    def test_blocks_over_limit(self):
        rl = RateLimiter(max_requests=3, window_seconds=60)
        for i in range(3):
            rl.allow("k", now=i)
        assert rl.allow("k", now=3) is False

    def test_window_slides(self):
        rl = RateLimiter(max_requests=2, window_seconds=10)
        assert rl.allow("k", now=0.0)
        assert rl.allow("k", now=1.0)
        assert rl.allow("k", now=5.0) is False
        # first hit (t=0) expires after t=10
        assert rl.allow("k", now=10.5) is True

    def test_keys_are_independent(self):
        rl = RateLimiter(max_requests=1, window_seconds=60)
        assert rl.allow("a", now=0)
        assert rl.allow("b", now=0)
        assert rl.allow("a", now=1) is False

    def test_remaining(self):
        rl = RateLimiter(max_requests=3, window_seconds=60)
        assert rl.remaining("k", now=0) == 3
        rl.allow("k", now=0)
        assert rl.remaining("k", now=1) == 2

    def test_reset_single_key(self):
        rl = RateLimiter(max_requests=1, window_seconds=60)
        rl.allow("k", now=0)
        rl.reset("k")
        assert rl.allow("k", now=1) is True

    def test_reset_all(self):
        rl = RateLimiter(max_requests=1, window_seconds=60)
        rl.allow("a", now=0)
        rl.allow("b", now=0)
        rl.reset()
        assert rl.allow("a", now=1)
        assert rl.allow("b", now=1)

    def test_invalid_config(self):
        with pytest.raises(ValueError):
            RateLimiter(max_requests=0)
        with pytest.raises(ValueError):
            RateLimiter(window_seconds=0)
