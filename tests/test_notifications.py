"""Tests for the WebSocket-based notification server."""

import asyncio
import json

import pytest
import websockets
from aiohttp import ClientSession

from notifications import (
    TYPE_BROADCAST,
    TYPE_DIRECT,
    TYPE_SYSTEM,
    ClientRegistry,
    NotificationServer,
    make_message,
)


@pytest.fixture
async def server():
    srv = NotificationServer(host="127.0.0.1", ws_port=0, rest_port=0)
    await srv.start()
    yield srv
    await srv.stop()


async def open_client(ws_port, timeout=5):
    return await asyncio.wait_for(
        websockets.connect(f"ws://127.0.0.1:{ws_port}"),
        timeout=timeout,
    )


async def recv_json(ws):
    raw = await asyncio.wait_for(ws.recv(), timeout=5)
    return json.loads(raw)


# ── ClientRegistry ───────────────────────────────────────────


def test_registry_add_assigns_unique_ids():
    registry = ClientRegistry()
    first = registry.add(object())
    second = registry.add(object())
    assert first != second
    assert registry.count == 2


def test_registry_remove():
    registry = ClientRegistry()
    cid = registry.add(object())
    assert registry.get(cid) is not None
    registry.remove(cid)
    assert registry.count == 0
    assert registry.get(cid) is None


def test_message_format():
    msg = make_message(TYPE_SYSTEM, {"client_id": "c1"})
    assert set(msg) == {"type", "payload", "timestamp"}
    assert msg["type"] == TYPE_SYSTEM
    assert msg["payload"] == {"client_id": "c1"}
    assert isinstance(msg["timestamp"], str)


# ── WebSocket behavior ──────────────────────────────────────


async def test_connect_assigns_unique_id(server):
    async with await open_client(server.ws_bound_port) as ws:
        first = await recv_json(ws)
        assert first["type"] == TYPE_SYSTEM
        assert "client_id" in first["payload"]
    async with await open_client(server.ws_bound_port) as ws:
        second = await recv_json(ws)
        assert second["type"] == TYPE_SYSTEM
        assert second["payload"]["client_id"] != first["payload"]["client_id"]


async def test_broadcast_reaches_all_clients(server):
    ws1 = await open_client(server.ws_bound_port)
    ws2 = await open_client(server.ws_bound_port)
    async with ws1, ws2:
        await recv_json(ws1)
        await recv_json(ws2)
        await ws1.send(json.dumps({
            "type": TYPE_BROADCAST,
            "payload": {"text": "hello everyone"},
        }))
        got1 = await recv_json(ws1)
        got2 = await recv_json(ws2)
        for got in (got1, got2):
            assert got["type"] == TYPE_BROADCAST
            assert got["payload"]["text"] == "hello everyone"
            assert "sender" in got["payload"]


async def test_direct_message(server):
    ws_sender = await open_client(server.ws_bound_port)
    ws_target = await open_client(server.ws_bound_port)
    ws_bystander = await open_client(server.ws_bound_port)
    async with ws_sender, ws_target, ws_bystander:
        sender_id = (await recv_json(ws_sender))["payload"]["client_id"]
        target_id = (await recv_json(ws_target))["payload"]["client_id"]
        await recv_json(ws_bystander)

        await ws_sender.send(json.dumps({
            "type": TYPE_DIRECT,
            "payload": {"target_id": target_id, "text": "psst"},
        }))
        got = await recv_json(ws_target)
        assert got["type"] == TYPE_DIRECT
        assert got["payload"]["text"] == "psst"
        assert got["payload"]["sender"] == sender_id

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws_bystander.recv(), timeout=0.5)


async def test_direct_to_missing_client_gets_error(server):
    async with await open_client(server.ws_bound_port) as ws:
        await recv_json(ws)
        await ws.send(json.dumps({
            "type": TYPE_DIRECT,
            "payload": {"target_id": "client-99999", "text": "nope"},
        }))
        got = await recv_json(ws)
        assert got["type"] == TYPE_SYSTEM
        assert "error" in got["payload"]


async def test_unsupported_type_reports_error(server):
    async with await open_client(server.ws_bound_port) as ws:
        await recv_json(ws)
        await ws.send(json.dumps({"type": "telepathy", "payload": {}}))
        got = await recv_json(ws)
        assert got["type"] == TYPE_SYSTEM
        assert "unsupported" in got["payload"]["error"]


async def test_invalid_json_reports_error(server):
    async with await open_client(server.ws_bound_port) as ws:
        await recv_json(ws)
        await ws.send("this is not json")
        got = await recv_json(ws)
        assert got["type"] == TYPE_SYSTEM
        assert "error" in got["payload"]


async def test_disconnect_removes_client_and_notifies(server):
    ws1 = await open_client(server.ws_bound_port)
    ws2 = await open_client(server.ws_bound_port)
    async with ws2:
        await recv_json(ws1)
        await recv_json(ws2)
        assert server.registry.count == 2

        await ws1.close()
        notified = await recv_json(ws2)
        assert notified["type"] == TYPE_SYSTEM
        assert notified["payload"]["message"] == "disconnected"
        assert server.registry.count == 1


# ── REST /health ────────────────────────────────────────────


async def test_health_returns_client_count(server):
    ws = await open_client(server.ws_bound_port)
    async with ws:
        await recv_json(ws)
        url = f"http://127.0.0.1:{server.rest_bound_port}/health"
        async with ClientSession() as session:
            async with session.get(url) as resp:
                assert resp.status == 200
                body = await resp.json()
                assert body["clients"] == 1

    async with ClientSession() as session:
        async with session.get(url) as resp:
            assert resp.status == 200
            body = await resp.json()
            assert body["clients"] == 0
