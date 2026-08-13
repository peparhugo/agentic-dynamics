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
    )
    await srv.start()
    yield srv
    srv.stop()
    await srv.wait_closed()
