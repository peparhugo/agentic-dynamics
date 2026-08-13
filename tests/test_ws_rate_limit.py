import asyncio
import json

import fakeredis
import pytest
import websockets

from notification_server.rate_limit import RateLimiter
from notification_server.ws_server import NotificationServer


@pytest.fixture
async def limited_server():
    redis_client = fakeredis.FakeAsyncRedis(server=fakeredis.FakeServer())
    rate_limiter = RateLimiter(redis_client, limit=2, window_seconds=60)
    server_wrapper = NotificationServer(rate_limiter=rate_limiter)
    ws_server = await server_wrapper.serve("localhost", 0)
    port = ws_server.sockets[0].getsockname()[1]
    yield server_wrapper, f"ws://localhost:{port}"
    ws_server.close()
    await ws_server.wait_closed()
    await redis_client.aclose()


def _broadcast(text):
    return json.dumps(
        {"type": "broadcast", "payload": {"text": text}, "timestamp": "2026-08-13T00:00:00Z"}
    )


async def test_messages_within_limit_are_delivered(limited_server):
    _server, uri = limited_server
    async with websockets.connect(uri) as ws:
        await ws.recv()  # connected ack
        await ws.send(_broadcast("one"))
        got = json.loads(await ws.recv())
        assert got["payload"]["text"] == "one"


async def test_exceeding_limit_returns_error_not_drop(limited_server):
    _server, uri = limited_server
    async with websockets.connect(uri) as ws:
        await ws.recv()  # connected ack

        await ws.send(_broadcast("one"))
        await ws.recv()
        await ws.send(_broadcast("two"))
        await ws.recv()

        # third message in the window exceeds the limit of 2
        await ws.send(_broadcast("three"))
        err = json.loads(await ws.recv())
        assert err["type"] == "system"
        assert err["payload"]["event"] == "error"
        assert "rate limit" in err["payload"]["message"]

        # connection is still open and usable for further (rejected) sends
        await ws.send(_broadcast("four"))
        err2 = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
        assert err2["payload"]["event"] == "error"


async def test_rate_limit_is_per_client(limited_server):
    _server, uri = limited_server
    async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
        await ws1.recv()
        await ws2.recv()

        await ws1.send(_broadcast("a"))
        await ws1.recv()
        await ws2.recv()  # broadcasts go to every connection, including ws2
        await ws1.send(_broadcast("b"))
        await ws1.recv()
        await ws2.recv()
        await ws1.send(_broadcast("c"))
        err = json.loads(await ws1.recv())
        assert err["payload"]["event"] == "error"

        # ws2 has not sent anything itself yet, so it still has its own budget
        await ws2.send(_broadcast("d"))
        got = json.loads(await ws2.recv())
        assert got["payload"]["text"] == "d"
