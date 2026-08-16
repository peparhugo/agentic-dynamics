"""Tests for the WebSocket-based notification server."""

import asyncio
import json

import pytest
import websockets
from aiohttp import ClientSession

from notifications import (
    TYPE_BROADCAST,
    TYPE_DIRECT,
    TYPE_SUBSCRIBE,
    TYPE_SYSTEM,
    TYPE_UNSUBSCRIBE,
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


# ── Channel subscriptions ──────────────────────────────────


def test_registry_subscribe_unsubscribe():
    registry = ClientRegistry()
    registry.subscribe("client-1", "alerts")
    registry.subscribe("client-2", "alerts")
    registry.subscribe("client-1", "system")
    assert registry.channel_members("alerts") == ["client-1", "client-2"]
    assert registry.channel_members("system") == ["client-1"]
    assert registry.channels() == [
        {"name": "alerts", "subscribers": 2},
        {"name": "system", "subscribers": 1},
    ]

    registry.unsubscribe("client-1", "alerts")
    assert registry.channel_members("alerts") == ["client-2"]
    registry.unsubscribe("client-2", "alerts")
    assert registry.channel_members("alerts") == []
    assert registry.channels() == [{"name": "system", "subscribers": 1}]


def test_registry_unsubscribe_all():
    registry = ClientRegistry()
    registry.subscribe("client-1", "alerts")
    registry.subscribe("client-1", "system")
    registry.unsubscribe_all("client-1")
    assert registry.channel_members("alerts") == []
    assert registry.channels() == []


async def test_subscribe_and_unsubscribe_confirmation(server):
    async with await open_client(server.ws_bound_port) as ws:
        await recv_json(ws)
        await ws.send(json.dumps({
            "type": TYPE_SUBSCRIBE,
            "payload": {"channel": "alerts"},
        }))
        got = await recv_json(ws)
        assert got["type"] == TYPE_SYSTEM
        assert got["payload"]["message"] == "subscribed"
        assert got["payload"]["channel"] == "alerts"

        await ws.send(json.dumps({
            "type": TYPE_UNSUBSCRIBE,
            "payload": {"channel": "alerts"},
        }))
        got = await recv_json(ws)
        assert got["type"] == TYPE_SYSTEM
        assert got["payload"]["message"] == "unsubscribed"
        assert got["payload"]["channel"] == "alerts"


async def test_subscribe_requires_channel(server):
    async with await open_client(server.ws_bound_port) as ws:
        await recv_json(ws)
        await ws.send(json.dumps({"type": TYPE_SUBSCRIBE, "payload": {}}))
        got = await recv_json(ws)
        assert got["type"] == TYPE_SYSTEM
        assert "error" in got["payload"]


async def test_channel_message_only_reaches_subscribers(server):
    subscriber = await open_client(server.ws_bound_port)
    bystander = await open_client(server.ws_bound_port)
    sender = await open_client(server.ws_bound_port)
    async with subscriber, bystander, sender:
        await recv_json(subscriber)
        await recv_json(bystander)
        await recv_json(sender)

        await subscriber.send(json.dumps({
            "type": TYPE_SUBSCRIBE,
            "payload": {"channel": "alerts"},
        }))
        await recv_json(subscriber)

        await sender.send(json.dumps({
            "type": TYPE_BROADCAST,
            "channel": "alerts",
            "payload": {"text": "critical"},
        }))

        got = await recv_json(subscriber)
        assert got["type"] == TYPE_BROADCAST
        assert got["payload"]["text"] == "critical"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(bystander.recv(), timeout=0.5)


async def test_channel_message_misses_unsubscribed(server):
    subscriber = await open_client(server.ws_bound_port)
    ex_member = await open_client(server.ws_bound_port)
    async with subscriber, ex_member:
        await recv_json(subscriber)
        await recv_json(ex_member)

        await subscriber.send(json.dumps({
            "type": TYPE_SUBSCRIBE,
            "payload": {"channel": "alerts"},
        }))
        await recv_json(subscriber)
        await ex_member.send(json.dumps({
            "type": TYPE_SUBSCRIBE,
            "payload": {"channel": "alerts"},
        }))
        await recv_json(ex_member)
        await ex_member.send(json.dumps({
            "type": TYPE_UNSUBSCRIBE,
            "payload": {"channel": "alerts"},
        }))
        await recv_json(ex_member)

        await subscriber.send(json.dumps({
            "type": TYPE_BROADCAST,
            "channel": "alerts",
            "payload": {"text": "solo"},
        }))
        got = await recv_json(subscriber)
        assert got["payload"]["text"] == "solo"
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ex_member.recv(), timeout=0.5)


async def test_client_can_subscribe_to_multiple_channels(server):
    ws = await open_client(server.ws_bound_port)
    async with ws:
        await recv_json(ws)
        for channel in ("alerts", "system", "chat"):
            await ws.send(json.dumps({
                "type": TYPE_SUBSCRIBE,
                "payload": {"channel": channel},
            }))
            got = await recv_json(ws)
            assert got["payload"]["channel"] == channel
        members = {
            c: server.registry.channel_members(c)
            for c in ("alerts", "system", "chat")
        }
        assert all(len(m) == 1 for m in members.values())


async def test_channel_routes_to_each_subscribed_channel(server):
    ws1 = await open_client(server.ws_bound_port)
    ws2 = await open_client(server.ws_bound_port)
    sender = await open_client(server.ws_bound_port)
    async with ws1, ws2, sender:
        await recv_json(ws1)
        await recv_json(ws2)
        await recv_json(sender)

        await ws1.send(json.dumps({
            "type": TYPE_SUBSCRIBE, "payload": {"channel": "alerts"},
        }))
        await recv_json(ws1)
        await ws1.send(json.dumps({
            "type": TYPE_SUBSCRIBE, "payload": {"channel": "chat"},
        }))
        await recv_json(ws1)
        await ws2.send(json.dumps({
            "type": TYPE_SUBSCRIBE, "payload": {"channel": "chat"},
        }))
        await recv_json(ws2)

        await sender.send(json.dumps({
            "type": TYPE_BROADCAST,
            "channel": "chat",
            "payload": {"text": "chat msg"},
        }))
        got1 = await recv_json(ws1)
        got2 = await recv_json(ws2)
        assert got1["payload"]["text"] == "chat msg"
        assert got2["payload"]["text"] == "chat msg"

        await sender.send(json.dumps({
            "type": TYPE_BROADCAST,
            "channel": "alerts",
            "payload": {"text": "alert msg"},
        }))
        got1 = await recv_json(ws1)
        assert got1["payload"]["text"] == "alert msg"
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws2.recv(), timeout=0.5)


async def test_no_channel_still_broadcasts_to_all(server):
    ws1 = await open_client(server.ws_bound_port)
    ws2 = await open_client(server.ws_bound_port)
    async with ws1, ws2:
        await recv_json(ws1)
        await recv_json(ws2)
        await ws1.send(json.dumps({
            "type": TYPE_SUBSCRIBE, "payload": {"channel": "alerts"},
        }))
        await recv_json(ws1)
        await ws1.send(json.dumps({
            "type": TYPE_BROADCAST,
            "payload": {"text": "everyone"},
        }))
        got1 = await recv_json(ws1)
        got2 = await recv_json(ws2)
        assert got1["payload"]["text"] == "everyone"
        assert got2["payload"]["text"] == "everyone"


async def test_disconnect_removes_channel_subscription(server):
    ws = await open_client(server.ws_bound_port)
    await recv_json(ws)
    await ws.send(json.dumps({
        "type": TYPE_SUBSCRIBE, "payload": {"channel": "alerts"},
    }))
    await recv_json(ws)
    assert server.registry.channel_members("alerts")
    await ws.close()
    await asyncio.sleep(0.2)
    assert server.registry.channel_members("alerts") == []


# ── REST /channels ─────────────────────────────────────────


async def test_channels_endpoint_lists_channels_and_counts(server):
    ws1 = await open_client(server.ws_bound_port)
    ws2 = await open_client(server.ws_bound_port)
    async with ws1, ws2:
        await recv_json(ws1)
        await recv_json(ws2)
        await ws1.send(json.dumps({
            "type": TYPE_SUBSCRIBE, "payload": {"channel": "alerts"},
        }))
        await recv_json(ws1)
        await ws2.send(json.dumps({
            "type": TYPE_SUBSCRIBE, "payload": {"channel": "alerts"},
        }))
        await recv_json(ws2)
        await ws1.send(json.dumps({
            "type": TYPE_SUBSCRIBE, "payload": {"channel": "chat"},
        }))
        await recv_json(ws1)

        url = f"http://127.0.0.1:{server.rest_bound_port}/channels"
        async with ClientSession() as session:
            async with session.get(url) as resp:
                assert resp.status == 200
                body = await resp.json()
                channels = {c["name"]: c["subscribers"] for c in body["channels"]}
                assert channels == {"alerts": 2, "chat": 1}


async def test_channel_subscribers_endpoint(server):
    ws = await open_client(server.ws_bound_port)
    async with ws:
        await recv_json(ws)
        await ws.send(json.dumps({
            "type": TYPE_SUBSCRIBE, "payload": {"channel": "system"},
        }))
        await recv_json(ws)

        url = (
            f"http://127.0.0.1:{server.rest_bound_port}"
            "/channels/system/subscribers"
        )
        async with ClientSession() as session:
            async with session.get(url) as resp:
                assert resp.status == 200
                body = await resp.json()
                assert body["channel"] == "system"
                assert len(body["subscribers"]) == 1
