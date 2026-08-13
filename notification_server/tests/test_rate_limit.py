import fakeredis.aioredis as fakeredis_asyncio
import pytest_asyncio

from notification_server.rate_limit import DEFAULT_RATE_LIMIT, RateLimiter, resolve_rate_limit


@pytest_asyncio.fixture
async def client():
    client = fakeredis_asyncio.FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


async def test_allows_messages_within_limit(client):
    limiter = RateLimiter(client, limit=3)
    for _ in range(3):
        assert await limiter.allow("client-1") is True


async def test_rejects_messages_over_limit(client):
    limiter = RateLimiter(client, limit=3)
    for _ in range(3):
        await limiter.allow("client-1")
    assert await limiter.allow("client-1") is False


async def test_limit_is_tracked_independently_per_client(client):
    limiter = RateLimiter(client, limit=1)
    assert await limiter.allow("client-1") is True
    assert await limiter.allow("client-2") is True
    assert await limiter.allow("client-1") is False
    assert await limiter.allow("client-2") is False


async def test_window_resets_after_expiry(client):
    limiter = RateLimiter(client, limit=1, window_seconds=60)
    assert await limiter.allow("client-1") is True
    assert await limiter.allow("client-1") is False
    # Simulate the window elapsing by clearing the counter directly, since
    # fakeredis TTLs don't advance with wall-clock time in tests.
    await client.delete("notification_server:ratelimit:client-1")
    assert await limiter.allow("client-1") is True


def test_resolve_rate_limit_prefers_explicit_argument(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "50")
    assert resolve_rate_limit(10) == 10


def test_resolve_rate_limit_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "25")
    assert resolve_rate_limit() == 25


def test_resolve_rate_limit_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT", raising=False)
    assert resolve_rate_limit() == DEFAULT_RATE_LIMIT
