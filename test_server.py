"""Tests for the WebSocket notification server."""

import asyncio
import json

import aiohttp
import pytest
from websockets.asyncio.client import connect

from server import NotificationServer, make_message


async def recv_json(ws, timeout=5.0):
    return json.loads(await asyncio.wait_for(ws.recv(), timeout))


async def recv_nothing(ws, timeout=0.2):
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(ws.recv(), timeout)


@pytest.fixture
async def server():
    srv = NotificationServer()
    await srv.start(host="localhost", port=0)
    port = srv._server.sockets[0].getsockname()[1]
    yield srv, port
    await srv.stop()


@pytest.fixture
async def client_factory(server):
    _, port = server

    async def make_client():
        ws = await connect(f"ws://localhost:{port}")
        welcome = await recv_json(ws)
        return ws, welcome

    return make_client


# ── Message format ─────────────────────────────────────────────


def test_make_message_has_expected_shape():
    msg = make_message("broadcast", {"text": "hi"})
    assert set(msg) == {"type", "payload", "timestamp"}
    assert msg["type"] == "broadcast"
    assert msg["payload"] == {"text": "hi"}
    assert isinstance(msg["timestamp"], str)


def test_make_message_rejects_unknown_type():
    with pytest.raises(ValueError):
        make_message("nope", {})


# ── Connection lifecycle ───────────────────────────────────────


async def test_connect_assigns_unique_ids(client_factory):
    ws1, welcome1 = await client_factory()
    ws2, welcome2 = await client_factory()

    assert welcome1["type"] == "system"
    assert welcome1["payload"]["event"] == "connected"
    assert welcome2["type"] == "system"
    assert welcome2["payload"]["event"] == "connected"
    assert welcome1["payload"]["client_id"] != welcome2["payload"]["client_id"]

    await ws1.close()
    await ws2.close()


async def test_client_count_reflects_connections(server, client_factory):
    srv, _ = server
    assert srv.client_count == 0

    ws1, _ = await client_factory()
    assert srv.client_count == 1

    ws2, _ = await client_factory()
    assert srv.client_count == 2

    await ws1.close()
    await ws2.close()


async def test_disconnect_cleans_up(server, client_factory):
    srv, _ = server
    ws, welcome = await client_factory()
    assert srv.client_count == 1

    await ws.close()

    for _ in range(50):
        if srv.client_count == 0:
            break
        await asyncio.sleep(0.01)
    assert srv.client_count == 0
    assert welcome["payload"]["client_id"] not in srv.client_ids


# ── Messaging ──────────────────────────────────────────────────


async def test_broadcast_reaches_all_clients(client_factory):
    ws1, _ = await client_factory()
    ws2, _ = await client_factory()
    ws3, _ = await client_factory()

    await ws1.send(json.dumps({"type": "broadcast", "payload": {"text": "hello"}}))

    for ws in (ws1, ws2, ws3):
        msg = await recv_json(ws)
        assert msg["type"] == "broadcast"
        assert msg["payload"] == {"text": "hello"}
        assert isinstance(msg["timestamp"], str)

    for ws in (ws1, ws2, ws3):
        await ws.close()


async def test_direct_message_goes_to_target_only(client_factory):
    ws_a, welcome_a = await client_factory()
    ws_b, welcome_b = await client_factory()

    target = welcome_b["payload"]["client_id"]
    await ws_a.send(
        json.dumps(
            {
                "type": "direct",
                "payload": {"target_id": target, "text": "psst"},
            }
        )
    )

    msg = await recv_json(ws_b)
    assert msg["type"] == "direct"
    assert msg["payload"] == {"target_id": target, "text": "psst"}

    await recv_nothing(ws_a)

    await ws_a.close()
    await ws_b.close()


async def test_direct_to_unknown_client_reports_error(client_factory):
    ws, _ = await client_factory()

    await ws.send(
        json.dumps({"type": "direct", "payload": {"target_id": "nope", "text": "hi"}})
    )

    msg = await recv_json(ws)
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "error"

    await ws.close()


async def test_server_broadcast_api(server, client_factory):
    srv, _ = server
    ws1, _ = await client_factory()
    ws2, _ = await client_factory()

    delivered = await srv.broadcast({"text": "announcement"})
    assert delivered == 2

    for ws in (ws1, ws2):
        msg = await recv_json(ws)
        assert msg["type"] == "broadcast"
        assert msg["payload"] == {"text": "announcement"}

    await ws1.close()
    await ws2.close()


async def test_server_direct_api(server, client_factory):
    srv, _ = server
    ws, welcome = await client_factory()
    target = welcome["payload"]["client_id"]

    ok = await srv.send_direct(target, {"text": "hi"})
    assert ok is True

    msg = await recv_json(ws)
    assert msg["type"] == "direct"
    assert msg["payload"] == {"text": "hi"}

    assert await srv.send_direct("missing", {"text": "hi"}) is False

    await ws.close()


async def test_invalid_json_is_rejected(client_factory):
    ws, _ = await client_factory()
    await ws.send("this is not json")

    msg = await recv_json(ws)
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "error"

    await ws.close()


# ── REST /health ───────────────────────────────────────────────


async def test_health_endpoint(server, client_factory):
    _, port = server
    ws, _ = await client_factory()

    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://localhost:{port}/health") as resp:
            assert resp.status == 200
            body = await resp.json()
    assert body["status"] == "ok"
    assert body["clients"] == 1

    await ws.close()


async def test_health_endpoint_zero_clients(server):
    _, port = server
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://localhost:{port}/health") as resp:
            assert resp.status == 200
            body = await resp.json()
    assert body["clients"] == 0
