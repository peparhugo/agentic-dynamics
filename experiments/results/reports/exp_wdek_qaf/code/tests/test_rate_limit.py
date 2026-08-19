"""Tests for rate limiting."""

import time

from shortener.rate_limit import RateLimiter


def test_limiter_allows_up_to_max():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    assert limiter.allow("ip") is True
    assert limiter.allow("ip") is True
    assert limiter.allow("ip") is True
    assert limiter.allow("ip") is False


def test_limiter_keys_are_independent():
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("a") is True
    assert limiter.allow("a") is False
    assert limiter.allow("b") is True


def test_limiter_window_resets():
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("ip") is True
    assert limiter.allow("ip") is False

    # Simulate the window elapsing.
    for key in limiter._windows:
        start, _ = limiter._windows[key]
        limiter._windows[key] = (start - 61, 1)

    assert limiter.allow("ip") is True


def test_limiter_reset():
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("ip") is True
    limiter.reset()
    assert limiter.allow("ip") is True


def test_shorten_rate_limited(client):
    # TestConfig.RATE_LIMIT_MAX == 5
    for _ in range(5):
        resp = client.post("/api/shorten", json={"url": "https://example.com"})
        assert resp.status_code == 201

    resp = client.post("/api/shorten", json={"url": "https://example.com"})
    assert resp.status_code == 429
    assert resp.get_json()["error"] == "rate limit exceeded"


def test_redirect_rate_limited(client):
    resp = client.post("/api/shorten", json={"url": "https://example.com"})
    code = resp.get_json()["short_code"]

    # One call already consumed by the POST above (shared per-IP limiter).
    for _ in range(4):
        r = client.get(f"/{code}")
        assert r.status_code == 302

    r = client.get(f"/{code}")
    assert r.status_code == 429
