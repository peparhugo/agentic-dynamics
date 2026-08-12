"""
Shared pytest fixtures.

The app's rate limiting is backed by Redis (Flask-Limiter), but the test
environment has no real Redis server. Every test transparently gets a
fresh, isolated in-memory ``fakeredis`` server in place of a real one by
monkeypatching ``redis.from_url`` -- the exact call the `limits` library's
Redis storage backend uses to connect. This exercises the same client
API/Lua-script-based atomic increments as production while staying fast
and dependency-free, and a brand new fake server per test means rate
limit counters can never leak between tests.
"""

import fakeredis
import pytest
import redis


@pytest.fixture(autouse=True)
def fake_redis_server(monkeypatch):
    server = fakeredis.FakeServer()

    def _fake_from_url(url, **kwargs):
        return fakeredis.FakeStrictRedis(server=server)

    monkeypatch.setattr(redis, "from_url", _fake_from_url)
    yield
