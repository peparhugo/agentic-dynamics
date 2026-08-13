import os
import tempfile

import fakeredis
import pytest
import pytest_asyncio
from websockets.asyncio.server import serve

from notification_server.broker import RedisBroker
from notification_server.persistence import MessageStore
from notification_server.server import NotificationServer


def make_notification_server(shared_fake_server=None):
    """Build a NotificationServer wired to an isolated fakeredis backend and
    a throwaway SQLite file, so tests never depend on a real Redis process.

    Passing `shared_fake_server` (a fakeredis.FakeServer) lets multiple
    NotificationServer instances share one in-memory Redis backend, which is
    how cross-instance pub/sub delivery is exercised in tests.
    """
    fake_server = shared_fake_server or fakeredis.FakeServer()
    client = fakeredis.FakeAsyncRedis(server=fake_server, decode_responses=True)
    broker = RedisBroker(client=client)

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = MessageStore(db_path)

    notification_server = NotificationServer(broker=broker, store=store)
    return notification_server, fake_server, db_path


async def _teardown(notification_server, db_path):
    await notification_server.close()
    os.remove(db_path)


@pytest.fixture
def notification_server_factory():
    """Returns `make_notification_server`, for tests that need multiple
    instances sharing one fake Redis backend (cross-instance scenarios)."""
    return make_notification_server


@pytest_asyncio.fixture
async def running_server():
    notification_server, _, db_path = make_notification_server()
    await notification_server.start()
    server = await serve(
        notification_server.handler,
        "localhost",
        0,
        process_request=notification_server.process_request,
    )
    port = server.sockets[0].getsockname()[1]
    uri = f"ws://localhost:{port}"
    health_url = f"http://localhost:{port}/health"
    try:
        yield notification_server, uri, health_url
    finally:
        server.close()
        await server.wait_closed()
        await _teardown(notification_server, db_path)
