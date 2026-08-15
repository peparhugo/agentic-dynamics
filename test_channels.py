"""Tests for channel-based subscriptions in the notification server."""

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


# ── Message types ──────────────────────────────────────────────


def test_make_message_supports_subscribe_and_unsubscribe():
    assert make_message("subscribe", {"channel": "alerts"})["type"] == "subscribe"
    assert make_message("unsubscribe", {"channel": "alerts"})["type"] == "unsubscribe"


# ── Channel subscribe/unsubscribe via WS ───────────────────────


async def test_subscribe_routes_channel_messages_to_subscribers(client_factory):
    ws_a, _ = await client_factory()
    ws_b, welcome_b = await client_factory()
    ws_c, _ = await client_factory()

    await ws_a.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
    await ws_c.send(json.dumps({"type": "subscribe", "channel": "alerts"}))

    await ws_b.send(
        json.dumps(
            {"type": "broadcast", "channel": "alerts", "payload": {"text": "fire!"}}
        )
    )

    for ws in (ws_a, ws_c):
        msg = await recv_json(ws)
        assert msg["type"] == "broadcast"
        assert msg["payload"] == {"text": "fire!"}

    await recv_nothing(ws_b)

    for ws in (ws_a, ws_b, ws_c):
        await ws.close()


async def test_channel_message_not_received_by_non_subscriber(client_factory):
    ws_a, _ = await client_factory()
    ws_b, _ = await client_factory()

    await ws_a.send(json.dumps({"type": "subscribe", "channel": "alerts"}))

    await ws_b.send(
        json.dumps(
            {"type": "broadcast", "channel": "chat", "payload": {"text": "hey"}}
        )
    )

    await recv_nothing(ws_a)

    await ws_a.close()
    await ws_b.close()


async def test_message_without_channel_still_broadcasts_to_all(client_factory):
    ws_a, _ = await client_factory()
    ws_b, _ = await client_factory()

    await ws_a.send(json.dumps({"type": "subscribe", "channel": "alerts"}))

    await ws_b.send(json.dumps({"type": "broadcast", "payload": {"text": "all"}}))

    for ws in (ws_a, ws_b):
        msg = await recv_json(ws)
        assert msg["payload"] == {"text": "all"}

    await ws_a.close()
    await ws_b.close()


async def test_client_can_be_subscribed_to_multiple_channels(client_factory):
    ws_a, _ = await client_factory()
    ws_b, _ = await client_factory()

    await ws_a.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
    await ws_a.send(json.dumps({"type": "subscribe", "channel": "chat"}))

    await ws_b.send(
        json.dumps(
            {"type": "broadcast", "channel": "alerts", "payload": {"text": "a"}}
        )
    )
    assert (await recv_json(ws_a))["payload"] == {"text": "a"}

    await ws_b.send(
        json.dumps(
            {"type": "broadcast", "channel": "chat", "payload": {"text": "c"}}
        )
    )
    assert (await recv_json(ws_a))["payload"] == {"text": "c"}

    await ws_a.close()
    await ws_b.close()


async def test_unsubscribe_stops_delivery(client_factory):
    ws_a, _ = await client_factory()
    ws_b, _ = await client_factory()

    await ws_a.send(json.dumps({"type": "subscribe", "channel": "alerts"}))

    await ws_b.send(
        json.dumps(
            {"type": "broadcast", "channel": "alerts", "payload": {"text": "one"}}
        )
    )
    assert (await recv_json(ws_a))["payload"] == {"text": "one"}

    await ws_a.send(json.dumps({"type": "unsubscribe", "channel": "alerts"}))

    await ws_b.send(
        json.dumps(
            {"type": "broadcast", "channel": "alerts", "payload": {"text": "two"}}
        )
    )
    await recv_nothing(ws_a)

    await ws_a.close()
    await ws_b.close()


async def test_subscribe_missing_channel_reports_error(client_factory):
    ws, _ = await client_factory()
    await ws.send(json.dumps({"type": "subscribe", "payload": {}}))

    msg = await recv_json(ws)
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "error"

    await ws.close()


# ── Server-side channel API ────────────────────────────────────


async def test_server_subscribe_broadcast_channel(server, client_factory):
    srv, _ = server
    ws1, welcome1 = await client_factory()
    ws2, _ = await client_factory()

    srv.subscribe(welcome1["payload"]["client_id"], "system")

    delivered = await srv.broadcast({"text": "tick"}, channel="system")
    assert delivered == 1

    msg = await recv_json(ws1)
    assert msg["payload"] == {"text": "tick"}
    await recv_nothing(ws2)

    await ws1.close()
    await ws2.close()


async def test_channel_subscribers_and_info(server, client_factory):
    srv, _ = server
    ws1, welcome1 = await client_factory()
    ws2, welcome2 = await client_factory()

    id1 = welcome1["payload"]["client_id"]
    id2 = welcome2["payload"]["client_id"]

    srv.subscribe(id1, "alerts")
    srv.subscribe(id2, "alerts")
    srv.subscribe(id2, "chat")

    assert srv.channel_subscribers("alerts") == sorted([id1, id2])
    assert srv.channel_subscribers("chat") == [id2]
    assert srv.channel_subscribers("nope") == []

    info = {c["name"]: c["subscribers"] for c in srv.channels_info()}
    assert info == {"alerts": 2, "chat": 1}

    await ws1.close()
    await ws2.close()


async def test_disconnect_removes_channel_subscription(server, client_factory):
    srv, _ = server
    ws, welcome = await client_factory()
    cid = welcome["payload"]["client_id"]

    srv.subscribe(cid, "alerts")
    assert srv.channel_subscribers("alerts") == [cid]

    await ws.close()
    for _ in range(50):
        if not srv.channel_names:
            break
        await asyncio.sleep(0.01)
    assert srv.channel_names == []


# ── REST endpoints ─────────────────────────────────────────────


async def test_rest_list_channels(server, client_factory):
    _, port = server
    ws, _ = await client_factory()

    await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
    await ws.send(json.dumps({"type": "subscribe", "channel": "chat"}))

    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://localhost:{port}/channels") as resp:
            assert resp.status == 200
            body = await resp.json()

    channels = {c["name"]: c["subscribers"] for c in body["channels"]}
    assert channels == {"alerts": 1, "chat": 1}

    await ws.close()


async def test_rest_channel_subscribers(server, client_factory):
    _, port = server
    ws, welcome = await client_factory()
    cid = welcome["payload"]["client_id"]

    await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"http://localhost:{port}/channels/alerts/subscribers"
        ) as resp:
            assert resp.status == 200
            body = await resp.json()

    assert body["channel"] == "alerts"
    assert body["subscribers"] == [cid]

    await ws.close()


async def test_rest_channel_subscribers_empty(server):
    _, port = server
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"http://localhost:{port}/channels/missing/subscribers"
        ) as resp:
            assert resp.status == 200
            body = await resp.json()
    assert body["subscribers"] == []
