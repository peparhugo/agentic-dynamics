import os

import fakeredis
import pytest
import redis


def _fake_from_url(uri, **options):
    return fakeredis.FakeStrictRedis(server=_shared_server, **options)


_shared_server = fakeredis.FakeServer()
redis.from_url = _fake_from_url

os.environ["RATE_LIMIT_STORAGE_URI"] = "redis://localhost:6379"

from app import app as app_module  # noqa: E402

app_module.config["RATELIMIT_STORAGE_URI"] = "redis://localhost:6379"


@pytest.fixture(autouse=True)
def _reset_rate_limiting():
    app_module.config["RATELIMIT_DEFAULT_LIMIT"] = "100 per minute"
    client = fakeredis.FakeStrictRedis(server=_shared_server)
    client.flushall()
    client.close()
    yield
