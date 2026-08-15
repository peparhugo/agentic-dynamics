import asyncio
import base64
import json

import pytest_asyncio
from websockets.asyncio.client import connect

from notification_server import NotificationServer, encode_frame, decode_frame

try:
    from websockets.asyncio.server import serve
except ImportError:  # pragma: no cover
    serve = None


@pytest_asyncio.fixture
async def server(tmp_path):
    """Start a NotificationServer on an ephemeral port and yield (app, port)."""
    app = NotificationServer(database_url=str(tmp_path / "messages.db"))
    async with serve(
        app.handler,
        "127.0.0.1",
        0,
        process_request=app.process_request,
    ) as ws_server:
        port = ws_server.sockets[0].getsockname()[1]
        yield app, port


@pytest_asyncio.fixture
async def client_factory(server):
    """Return a factory producing connected websocket clients."""
    _, port = server
    connections = []

    async def _connect():
        ws = await connect(f"ws://127.0.0.1:{port}")
        connections.append(ws)
        return ws

    yield _connect

    for ws in connections:
        try:
            await ws.close()
        except Exception:
            pass


@pytest_asyncio.fixture
async def redis_backbone():
    """Provide a shared in-process Redis server (fakeredis) as the backbone."""
    import fakeredis.aioredis as fakeredis_aioredis

    yield fakeredis_aioredis.FakeServer()


@pytest_asyncio.fixture
async def redis_server_factory(redis_backbone):
    """Return a factory that starts Redis-backed NotificationServer instances.

    Every instance created by the factory shares the same in-process Redis
    backbone, mirroring how multiple real server processes share a single
    Redis server.
    """
    import fakeredis.aioredis as fakeredis_aioredis

    servers = []

    async def _factory(database_path=None):
        client = fakeredis_aioredis.FakeRedis(
            server=redis_backbone, decode_responses=True
        )
        app = NotificationServer(redis_client=client, database_url=database_path)
        await app.start()
        ws_server = await serve(
            app.handler,
            "127.0.0.1",
            0,
            process_request=app.process_request,
        )
        port = ws_server.sockets[0].getsockname()[1]
        servers.append((ws_server, app, client))
        return app, port

    yield _factory

    for ws_server, app, client in servers:
        ws_server.close()
        await ws_server.wait_closed()
        await app.stop()
        try:
            await client.aclose()
        except Exception:
            pass


async def recv_message(ws):
    """Receive one frame and decode the base64 JSON message."""
    raw = await ws.recv()
    return json.loads(base64.b64decode(raw).decode("utf-8"))


async def send_message(ws, message):
    """Encode a message as a base64 JSON frame and send it."""
    await ws.send(
        base64.b64encode(json.dumps(message).encode("utf-8")).decode("ascii")
    )


async def http_get(port, path="/health"):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    writer.write(request.encode())
    await writer.drain()
    data = await reader.read()
    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass
    return data.decode("utf-8")


def parse_http(raw):
    head, _, body = raw.partition("\r\n\r\n")
    status_line = head.split("\r\n", 1)[0]
    status = int(status_line.split(" ", 2)[1])
    return status, body
