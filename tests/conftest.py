import pytest_asyncio
from websockets.asyncio.server import serve

from notification_server.server import NotificationServer


@pytest_asyncio.fixture
async def running_server():
    notification_server = NotificationServer()
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
