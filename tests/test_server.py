import asyncio
import base64
import json
import urllib.request

import pytest
import websockets

from notification_server import NotificationServer, decode_message, encode_message


@pytest.fixture
async def server():
    srv = NotificationServer()
    await srv.start(port=0)
    yield srv
    await srv.stop()


def ws_url(server):
    return f"ws://127.0.0.1:{server.port}"


def health_url(server):
    return f"http://127.0.0.1:{server.port}/health"


def _get(url):
    with urllib.request.urlopen(url) as response:
        return response.read().decode("utf-8")


async def connected_count(server):
    body = await asyncio.to_thread(_get, health_url(server))
    return json.loads(body)["connected_clients"]


async def wait_for_count(server, expected, timeout=2.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        if await connected_count(server) == expected:
            return
        if loop.time() > deadline:
            raise AssertionError(f"client count never reached {expected}")
        await asyncio.sleep(0.05)


async def test_connect_assigns_unique_id(server):
    async with websockets.connect(ws_url(server)) as ws1, websockets.connect(
        ws_url(server)
    ) as ws2:
        msg1 = decode_message(await ws1.recv())
        msg2 = decode_message(await ws2.recv())

    assert msg1["type"] == "system"
    assert msg2["type"] == "system"
    assert msg1["payload"]["client_id"] != msg2["payload"]["client_id"]


async def test_broadcast_reaches_all_clients(server):
    async with websockets.connect(ws_url(server)) as ws1, websockets.connect(
        ws_url(server)
    ) as ws2, websockets.connect(ws_url(server)) as ws3:
        for ws in (ws1, ws2, ws3):
            await ws.recv()

        await ws1.send(
            encode_message(
                {"type": "broadcast", "payload": {"text": "hello"}, "timestamp": "t"}
            )
        )

        for ws in (ws1, ws2, ws3):
            got = decode_message(await ws.recv())
            assert got["type"] == "broadcast"
            assert got["payload"]["text"] == "hello"


async def test_direct_message_only_target_receives(server):
    async with websockets.connect(ws_url(server)) as ws1, websockets.connect(
        ws_url(server)
    ) as ws2:
        msg1 = decode_message(await ws1.recv())
        msg2 = decode_message(await ws2.recv())
        target = msg2["payload"]["client_id"]

        await ws1.send(
            encode_message(
                {
                    "type": "direct",
                    "payload": {"client_id": target, "text": "hi"},
                    "timestamp": "t",
                }
            )
        )

        got = decode_message(await ws2.recv())
        assert got["type"] == "direct"
        assert got["payload"]["text"] == "hi"
        assert got["payload"]["sender_id"] == msg1["payload"]["client_id"]


async def test_health_reports_connected_count(server):
    assert await connected_count(server) == 0

    async with websockets.connect(ws_url(server)) as ws:
        await ws.recv()
        assert await connected_count(server) == 1

    await wait_for_count(server, 0)


async def test_disconnect_removes_client(server):
    async with websockets.connect(ws_url(server)) as ws:
        await ws.recv()
        assert await connected_count(server) == 1

    await wait_for_count(server, 0)


async def test_wire_frames_are_base64(server):
    async with websockets.connect(ws_url(server)) as ws:
        raw = await ws.recv()

    assert isinstance(raw, str)
    json_bytes = base64.b64decode(raw.encode("ascii"))
    message = json.loads(json_bytes.decode("utf-8"))
    assert message["type"] == "system"
    assert "client_id" in message["payload"]
