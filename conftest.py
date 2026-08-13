"""
Shared pytest fixtures.

Flask-Limiter is backed by a real Redis instance (see tasks_api.py), so
counters persist across test runs unless cleared. This autouse fixture
flushes the dedicated rate-limit database before and after every test so
tests don't leak rate-limit state into each other.
"""

import redis
import pytest

RATE_LIMIT_TEST_REDIS_URL = "redis://localhost:6379/2"


@pytest.fixture(autouse=True)
def _flush_rate_limit_storage():
    client = redis.Redis.from_url(RATE_LIMIT_TEST_REDIS_URL)
    client.flushdb()
    yield
    client.flushdb()
