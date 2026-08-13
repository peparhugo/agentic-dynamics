"""Tests for the WebSocket-based notification server."""

import asyncio
import json

import aiohttp
import pytest
import websockets

from server import NotificationServer, build_message, utc_now


@pytest.fixture
async def server():
    """Start a NotificationServer on an ephemeral port and yield it."""
    srv = NotificationServer(host="127.0.0.1", port=0)
    await srv.start()
    try:
        yield srv
    finally:
        await srv.close()


@pytest.fixture
def ws_url(server):
    return f"ws://127.0.0.1:{server.bound_port}"


async def connect_client(ws_url):
    """Connect a client and consume its initial 'connected' system message."""
    ws = await websockets.connect(ws_url)
    raw = await asyncio.wait_for(ws.recv(), timeout=5)
    msg = json.loads(raw)
    assert msg["type"] == "system"
    assert "client_id" in msg["payload"]
    return ws, msg["payload"]["client_id"]


async def http_get(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return resp.status, await resp.json()


# ── Core features ─────────────────────────────────────────────────


async def test_client_connects_and_gets_unique_id(ws_url):
    ws1, id1 = await connect_client(ws_url)
    ws2, id2 = await connect_client(ws_url)
    try:
        assert id1.startswith("client-")
        assert id2.startswith("client-")
        assert id1 != id2
    finally:
        await ws1.close()
        await ws2.close()


async def test_broadcast_reaches_all_connected_clients(ws_url):
    ws1, _ = await connect_client(ws_url)
    ws2, _ = await connect_client(ws_url)
    try:
        payload = {"text": "hello everyone", "n": 1}
        await ws1.send(json.dumps({"type": "broadcast", "payload": payload}))

        received = [json.loads(await ws1.recv()), json.loads(await ws2.recv())]
        for msg in received:
            assert msg["type"] == "broadcast"
            assert msg["payload"] == payload
            assert isinstance(msg["timestamp"], str) and msg["timestamp"]
    finally:
        await ws1.close()
        await ws2.close()


async def test_direct_message_routed_only_to_target(ws_url):
    ws1, id1 = await connect_client(ws_url)
    ws2, id2 = await connect_client(ws_url)
    try:
        payload = {"target": id2, "text": "private hello"}
        await ws1.send(json.dumps({"type": "direct", "payload": payload}))

        msg = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))
        assert msg["type"] == "direct"
        assert msg["payload"] == payload

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws1.recv(), timeout=0.3)
    finally:
        await ws1.close()
        await ws2.close()


async def test_direct_to_unknown_target_does_not_crash(ws_url):
    ws1, _ = await connect_client(ws_url)
    try:
        await ws1.send(
            json.dumps(
                {"type": "direct", "payload": {"target": "does-not-exist", "text": "x"}}
            )
        )
        await asyncio.sleep(0.1)
    finally:
        await ws1.close()


async def test_disconnect_removes_client_cleanly(ws_url, server):
    ws, _ = await connect_client(ws_url)
    assert await server.registry.count() == 1
    await ws.close()
    for _ in range(50):
        if await server.registry.count() == 0:
            break
        await asyncio.sleep(0.02)
    assert await server.registry.count() == 0


async def test_health_endpoint_reports_client_count(ws_url, server):
    status, body = await http_get(f"http://127.0.0.1:{server.bound_port}/health")
    assert status == 200
    assert body["status"] == "ok"
    assert body["clients"] == 0

    ws1, _ = await connect_client(ws_url)
    ws2, _ = await connect_client(ws_url)
    try:
        status, body = await http_get(f"http://127.0.0.1:{server.bound_port}/health")
        assert status == 200
        assert body["clients"] == 2
    finally:
        await ws1.close()
        await ws2.close()
        await asyncio.sleep(0.1)

    status, body = await http_get(f"http://127.0.0.1:{server.bound_port}/health")
    assert status == 200
    assert body["clients"] == 0


# ── Message format ────────────────────────────────────────────────


async def test_message_envelope_has_exact_shape(ws_url):
    ws, _ = await connect_client(ws_url)
    try:
        await ws.send(json.dumps({"type": "broadcast", "payload": {"k": "v"}}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert set(msg.keys()) == {"type", "payload", "timestamp"}
        assert isinstance(msg["type"], str)
        assert isinstance(msg["payload"], dict)
        assert isinstance(msg["timestamp"], str)
    finally:
        await ws.close()


async def test_server_generated_system_message_on_connect(ws_url):
    ws = await websockets.connect(ws_url)
    try:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert msg["type"] == "system"
        assert set(msg.keys()) == {"type", "payload", "timestamp"}
        assert msg["payload"]["event"] == "connected"
    finally:
        await ws.close()


async def test_unknown_type_gets_system_error(ws_url):
    ws, _ = await connect_client(ws_url)
    try:
        await ws.send(json.dumps({"type": "mystery", "payload": {}}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert msg["type"] == "system"
        assert "error" in msg["payload"]
    finally:
        await ws.close()


async def test_malformed_json_gets_system_error(ws_url):
    ws, _ = await connect_client(ws_url)
    try:
        await ws.send("this is not json")
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert msg["type"] == "system"
        assert "error" in msg["payload"]
    finally:
        await ws.close()


# ── Server API helpers ────────────────────────────────────────────


async def test_broadcast_method(ws_url, server):
    ws1, _ = await connect_client(ws_url)
    ws2, _ = await connect_client(ws_url)
    try:
        message = build_message("system", {"event": "maintenance"})
        await server.broadcast(message)
        for ws in (ws1, ws2):
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert msg["type"] == "system"
            assert msg["payload"] == {"event": "maintenance"}
    finally:
        await ws1.close()
        await ws2.close()


async def test_send_direct_method(ws_url, server):
    ws1, _ = await connect_client(ws_url)
    ws2, id2 = await connect_client(ws_url)
    try:
        message = build_message("direct", {"to": id2, "text": "hi"})
        delivered = await server.send_direct(id2, message)
        assert delivered is True
        msg = json.loads(await asyncio.wait_for(ws2.recv(), timeout=5))
        assert msg == message

        missing = await server.send_direct("no-such-client", message)
        assert missing is False
    finally:
        await ws1.close()
        await ws2.close()


async def test_build_message_shape():
    message = build_message("system", {"event": "x"})
    assert set(message.keys()) == {"type", "payload", "timestamp"}
    assert message["type"] == "system"
    assert message["payload"] == {"event": "x"}
    assert message["timestamp"]
    assert utc_now()
