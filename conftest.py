import pytest_asyncio

from notification_server import NotificationServer


@pytest_asyncio.fixture
async def server():
    srv = NotificationServer(host="127.0.0.1", port=0)
    await srv.start()
    yield srv
    await srv.stop()
