"""Shared pytest fixtures.

Points rate limiting at a dedicated Redis instance for the test suite (kept
separate from whatever Redis the app uses in dev/prod) and flushes it before
each test so per-user request counts from one test never bleed into another.
"""

import os

os.environ.setdefault("RATELIMIT_STORAGE_URI", "redis://localhost:6399/0")

import pytest
import redis


@pytest.fixture(autouse=True)
def _flush_rate_limit_storage():
    client = redis.Redis.from_url(os.environ["RATELIMIT_STORAGE_URI"])
    client.flushdb()
    yield
