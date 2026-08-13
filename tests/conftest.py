import os
import tempfile
from contextlib import asynccontextmanager

import fakeredis
import pytest
import pytest_asyncio
from websockets.asyncio.server import serve

from notification_server.broker import RedisBroker
from notification_server.persistence import MessageStore
from notification_server.server import NotificationServer


def make_notification_server(shared_fake_server=None, **server_kwargs):
    """Build a NotificationServer wired to an isolated fakeredis backend and
    a throwaway SQLite file, so tests never depend on a real Redis process.

    Passing `shared_fake_server` (a fakeredis.FakeServer) lets multiple
    NotificationServer instances share one in-memory Redis backend, which is
    how cross-instance pub/sub delivery is exercised in tests.

    Extra `server_kwargs` (e.g. `rate_limit`, `message_ttl_days`,
    `cleanup_interval_seconds`) are forwarded to the NotificationServer
    constructor, overriding the env-var-derived defaults for that instance.
    """
    fake_server = shared_fake_server or fakeredis.FakeServer()
    client = fakeredis.FakeAsyncRedis(server=fake_server, decode_responses=True)
    broker = RedisBroker(client=client)

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = MessageStore(db_path)

    notification_server = NotificationServer(broker=broker, store=store, **server_kwargs)
    return notification_server, fake_server, db_path


async def _teardown(notification_server, db_path):
    await notification_server.close()
    os.remove(db_path)


@pytest.fixture
def notification_server_factory():
    """Returns `make_notification_server`, for tests that need multiple
    instances sharing one fake Redis backend (cross-instance scenarios)."""
    return make_notification_server


@asynccontextmanager
async def _running_server(**server_kwargs):
    notification_server, _, db_path = make_notification_server(**server_kwargs)
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


@pytest_asyncio.fixture
async def running_server():
    async with _running_server() as ctx:
        yield ctx


@pytest.fixture
def running_server_factory():
    """Returns an async context manager factory, for tests that need a
    running server built with non-default kwargs (e.g. a low `rate_limit`
    or a short `cleanup_interval_seconds` for fast, deterministic tests):

        async with running_server_factory(rate_limit=3) as (server, uri, health_url):
            ...
    """
    return _running_server
