import pytest
from fakeredis import aioredis as fakeredis_aioredis

from notification_server.rate_limiter import RateLimiter


async def test_allows_messages_up_to_the_limit():
    limiter = RateLimiter(limit=3)
    assert await limiter.check("client-a") is True
    assert await limiter.check("client-a") is True
    assert await limiter.check("client-a") is True


async def test_rejects_messages_once_limit_is_exceeded():
    limiter = RateLimiter(limit=3)
    for _ in range(3):
        assert await limiter.check("client-a") is True
    assert await limiter.check("client-a") is False
    # still rejected, not just a one-time trip
    assert await limiter.check("client-a") is False


async def test_limits_are_tracked_independently_per_client():
    limiter = RateLimiter(limit=1)
    assert await limiter.check("client-a") is True
    assert await limiter.check("client-b") is True
    assert await limiter.check("client-a") is False
    assert await limiter.check("client-b") is False


async def test_default_limit_is_100():
    limiter = RateLimiter()
    assert limiter.limit == 100


async def test_redis_backed_limiter_rejects_over_limit():
    redis_client = fakeredis_aioredis.FakeRedis()
    limiter = RateLimiter(redis_client=redis_client, limit=2)
    assert await limiter.check("client-a") is True
    assert await limiter.check("client-a") is True
    assert await limiter.check("client-a") is False


async def test_redis_backed_limiter_uses_a_shared_counter_key():
    redis_client = fakeredis_aioredis.FakeRedis()
    limiter = RateLimiter(redis_client=redis_client, limit=5)
    await limiter.check("client-a")
    await limiter.check("client-a")
    keys = [k.decode() for k in await redis_client.keys("notification_server:ratelimit:client-a:*")]
    assert len(keys) == 1
    assert await redis_client.get(keys[0]) == b"2"


async def test_redis_backed_limiter_shares_counters_across_instances():
    redis_client = fakeredis_aioredis.FakeRedis()
    limiter_a = RateLimiter(redis_client=redis_client, limit=2)
    limiter_b = RateLimiter(redis_client=redis_client, limit=2)
    assert await limiter_a.check("client-a") is True
    assert await limiter_b.check("client-a") is True
    # third message anywhere in the cluster trips the shared limit
    assert await limiter_a.check("client-a") is False


async def test_redis_backed_limiter_isolates_clients():
    redis_client = fakeredis_aioredis.FakeRedis()
    limiter = RateLimiter(redis_client=redis_client, limit=1)
    assert await limiter.check("client-a") is True
    assert await limiter.check("client-b") is True
    assert await limiter.check("client-a") is False
    assert await limiter.check("client-b") is False
