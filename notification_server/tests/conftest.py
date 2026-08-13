import pytest_asyncio
from fakeredis.aioredis import FakeRedis, FakeServer

from notification_server.server import NotificationServer


@pytest_asyncio.fixture
async def server(tmp_path):
    # Give every test its own FakeServer: FakeRedis() with no explicit
    # `server=` falls back to a process-wide singleton keyed by connection
    # URL, which would otherwise leak presence/pubsub state across tests.
    srv = NotificationServer(
        host="localhost",
        port=0,
        redis_client=FakeRedis(server=FakeServer(), decode_responses=True),
        db_path=str(tmp_path / "notifications.db"),
        # A very long cleanup interval so the background task fires once at
        # startup and then stays out of the way; tests that care about
        # expiry call server._run_cleanup() directly instead of waiting.
        cleanup_interval_seconds=10_000,
    )
    await srv.start()
    yield srv
    srv.stop()
    await srv.wait_closed()


@pytest_asyncio.fixture
async def make_server(tmp_path):
    """Factory fixture for tests that need non-default construction
    (e.g. a tight RATE_LIMIT). Each server gets its own FakeServer so
    state never leaks between instances created by the same test."""
    created = []

    async def _make(**overrides):
        kwargs = dict(
            host="localhost",
            port=0,
            redis_client=FakeRedis(server=FakeServer(), decode_responses=True),
            db_path=str(tmp_path / f"notifications-{len(created)}.db"),
            cleanup_interval_seconds=10_000,
        )
        kwargs.update(overrides)
        srv = NotificationServer(**kwargs)
        await srv.start()
        created.append(srv)
        return srv

    yield _make

    for srv in created:
        srv.stop()
        await srv.wait_closed()
