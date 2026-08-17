"""Tests for the WebSocket notification server."""

import asyncio
import json
import urllib.request

import pytest
import websockets

from notification_server import (
    NotificationServer,
    decode_message,
    encode_message,
)


@pytest.fixture
async def server():
    """Start a NotificationServer on an ephemeral port and yield it."""
    ns = NotificationServer()
    async with websockets.serve(
        ns.handler, "127.0.0.1", 0, process_request=ns.process_request
    ) as ws_server:
        port = ws_server.sockets[0].getsockname()[1]
        yield ns, port


async def connect_client(port):
    """Connect a client and consume its initial system 'connected' message."""
    ws = await websockets.connect(f"ws://127.0.0.1:{port}")
    raw = await asyncio.wait_for(ws.recv(), timeout=5)
    msg = decode_message(raw)
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "connected"
    return ws, msg["payload"]["client_id"]


async def send_message(ws, message):
    await ws.send(encode_message(message))


async def recv_message(ws, timeout=5):
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
    return decode_message(raw)


async def get_health(port):
    url = f"http://127.0.0.1:{port}/health"
    resp = await asyncio.to_thread(urllib.request.urlopen, url)
    return json.loads(resp.read().decode("utf-8"))


async def wait_for_clients(port, expected, timeout=5):
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        data = await get_health(port)
        if data["connected_clients"] == expected:
            return data
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(
                f"expected {expected} clients, got {data['connected_clients']}"
            )
        await asyncio.sleep(0.05)


def test_encode_decode_roundtrip():
    msg = {"type": "broadcast", "payload": {"text": "hi"}, "timestamp": "t"}
    assert decode_message(encode_message(msg)) == msg


def test_registry_operations():
    reg = NotificationServer().registry
    assert len(reg) == 0
    reg.add("a", object())
    reg.add("b", object())
    assert len(reg) == 2
    assert "a" in reg and "b" in reg
    assert set(reg.ids()) == {"a", "b"}
    reg.remove("a")
    assert "a" not in reg and len(reg) == 1


async def test_health_initial_zero(server):
    ns, port = server
    data = await get_health(port)
    assert data == {"connected_clients": 0}
    assert len(ns.registry) == 0


async def test_client_receives_unique_id(server):
    ns, port = server
    ws, client_id = await connect_client(port)
    assert isinstance(client_id, str) and client_id
    await ws.close()


async def test_two_clients_get_distinct_ids(server):
    ns, port = server
    ws1, id1 = await connect_client(port)
    ws2, id2 = await connect_client(port)
    assert id1 != id2
    await ws1.close()
    await ws2.close()


async def test_broadcast_reaches_all_clients(server):
    ns, port = server
    ws1, id1 = await connect_client(port)
    ws2, id2 = await connect_client(port)

    message = {"type": "broadcast", "payload": {"text": "hello"}, "timestamp": "t"}
    await send_message(ws1, message)

    received1 = await recv_message(ws1)
    received2 = await recv_message(ws2)
    for received in (received1, received2):
        assert received["type"] == "broadcast"
        assert received["payload"]["text"] == "hello"

    await ws1.close()
    await ws2.close()


async def test_direct_message_routes_to_target_only(server):
    ns, port = server
    ws1, id1 = await connect_client(port)
    ws2, id2 = await connect_client(port)

    message = {
        "type": "direct",
        "payload": {"to": id2, "text": "just for you"},
        "timestamp": "t",
    }
    await send_message(ws1, message)

    received = await recv_message(ws2)
    assert received["type"] == "direct"
    assert received["payload"]["text"] == "just for you"

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws1.recv(), timeout=0.3)

    await ws1.close()
    await ws2.close()


async def test_disconnect_removes_client(server):
    ns, port = server
    ws, client_id = await connect_client(port)
    await wait_for_clients(port, 1)

    await ws.close()
    await ws.wait_closed()
    await wait_for_clients(port, 0)
    assert len(ns.registry) == 0


async def test_health_reflects_multiple_clients(server):
    ns, port = server
    ws1, _ = await connect_client(port)
    ws2, _ = await connect_client(port)
    await wait_for_clients(port, 2)
    data = await get_health(port)
    assert data["connected_clients"] == 2
    await ws1.close()
    await ws2.close()
