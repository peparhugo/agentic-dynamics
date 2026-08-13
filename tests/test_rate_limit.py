import fakeredis
import pytest

from notification_server.rate_limit import RateLimiter


@pytest.fixture
def fake_server():
    return fakeredis.FakeServer()


def make_limiter(fake_server, limit=3, window_seconds=60):
    client = fakeredis.FakeAsyncRedis(server=fake_server)
    return RateLimiter(client, limit=limit, window_seconds=window_seconds)


async def test_allows_messages_up_to_the_limit(fake_server):
    limiter = make_limiter(fake_server, limit=3)
    results = [await limiter.allow("client-a") for _ in range(3)]
    assert results == [True, True, True]


async def test_rejects_messages_past_the_limit(fake_server):
    limiter = make_limiter(fake_server, limit=3)
    for _ in range(3):
        await limiter.allow("client-a")
    assert await limiter.allow("client-a") is False


async def test_limits_are_tracked_per_client(fake_server):
    limiter = make_limiter(fake_server, limit=2)
    await limiter.allow("client-a")
    await limiter.allow("client-a")
    assert await limiter.allow("client-a") is False
    # a different client has its own untouched budget
    assert await limiter.allow("client-b") is True


async def test_window_resets_after_expiry(fake_server):
    limiter = make_limiter(fake_server, limit=1, window_seconds=60)
    client = limiter._redis
    assert await limiter.allow("client-a") is True
    assert await limiter.allow("client-a") is False
    # simulate the window elapsing by deleting the counter key directly
    await client.delete("ratelimit:client-a")
    assert await limiter.allow("client-a") is True


async def test_sets_expiry_on_first_message_only(fake_server):
    limiter = make_limiter(fake_server, limit=5, window_seconds=42)
    client = limiter._redis
    await limiter.allow("client-a")
    ttl = await client.ttl("ratelimit:client-a")
    assert 0 < ttl <= 42


def test_from_env_reads_rate_limit_var(fake_server, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT", "250")
    client = fakeredis.FakeAsyncRedis(server=fake_server)
    limiter = RateLimiter.from_env(client)
    assert limiter.limit == 250


def test_from_env_defaults_to_100(fake_server, monkeypatch):
    monkeypatch.delenv("RATE_LIMIT", raising=False)
    client = fakeredis.FakeAsyncRedis(server=fake_server)
    limiter = RateLimiter.from_env(client)
    assert limiter.limit == 100
