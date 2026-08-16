"""Tests for channel-based subscriptions."""

import asyncio
import json
import urllib.request

import pytest
import websockets

from notification_server import NotificationServer, make_message


def parse(raw) -> dict:
    return json.loads(raw)


async def http_get(url: str) -> dict:
    def _get() -> dict:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read())

    return await asyncio.to_thread(_get)


@pytest.fixture
async def server():
    srv = await NotificationServer().start()
    yield srv
    await srv.stop()


@pytest.fixture
async def client(server):
    ws = await websockets.connect(server.ws_url)
    hello = parse(await ws.recv())
    yield ws, hello["payload"]["client_id"]
    await ws.close()


# ── Registry ───────────────────────────────────────────────────────

async def test_subscribe_unsubscribe_lifecycle(server):
    reg = server.registry
    a, b = object(), object()
    id_a = reg.add(a)
    id_b = reg.add(b)

    reg.subscribe(id_a, "alerts")
    reg.subscribe(id_a, "system")
    reg.subscribe(id_b, "alerts")
    assert reg.channels() == {"alerts": 2, "system": 1}
    assert reg.channel_subscribers("alerts") == {id_a, id_b}
    assert reg.channel_subscribers("system") == {id_a}

    reg.unsubscribe(id_a, "alerts")
    assert reg.channels() == {"alerts": 1, "system": 1}
    reg.unsubscribe(id_a, "nope")  # idempotent
    assert reg.channels() == {"alerts": 1, "system": 1}

    reg.remove(id_b)
    assert reg.channels() == {"system": 1}


# ── Subscribe / unsubscribe over the wire ──────────────────────────

async def test_subscribe_and_receive_channel_message(client, server):
    subscriber, sub_id = client
    async with websockets.connect(server.ws_url) as sender:
        sender_id = parse(await sender.recv())["payload"]["client_id"]

        await subscriber.send(
            json.dumps(make_message("subscribe", {"channel": "alerts"}))
        )
        await asyncio.sleep(0.05)

        await sender.send(
            json.dumps(
                {
                    "type": "broadcast",
                    "channel": "alerts",
                    "payload": {"text": "urgent"},
                }
            )
        )
        msg = parse(await asyncio.wait_for(subscriber.recv(), timeout=3))
        assert msg["type"] == "broadcast"
        assert msg["channel"] == "alerts"
        assert msg["payload"]["text"] == "urgent"
        assert msg["payload"]["channel"] == "alerts"
        assert msg["payload"]["from"] == sender_id


async def test_channel_message_does_not_reach_others(client, server):
    subscriber, _ = client
    async with websockets.connect(server.ws_url) as non_sub:
        await non_sub.recv()

        await subscriber.send(
            json.dumps(make_message("subscribe", {"channel": "alerts"}))
        )
        await asyncio.sleep(0.05)

        await non_sub.send(
            json.dumps(
                make_message("broadcast", {"channel": "alerts", "text": "x"})
            )
        )
        msg = parse(await asyncio.wait_for(subscriber.recv(), timeout=3))
        assert msg["payload"]["text"] == "x"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(non_sub.recv(), timeout=0.3)


async def test_broadcast_without_channel_still_goes_to_all(client, server):
    a, _ = client
    async with websockets.connect(server.ws_url) as b:
        await b.recv()
        await a.send(
            json.dumps(make_message("broadcast", {"text": "everyone"}))
        )
        for ws in (a, b):
            msg = parse(await asyncio.wait_for(ws.recv(), timeout=3))
            assert msg["type"] == "broadcast"
            assert msg["payload"]["text"] == "everyone"


async def test_multiple_channels_per_client(server):
    async with websockets.connect(server.ws_url) as ws:
        cid = parse(await ws.recv())["payload"]["client_id"]
        await ws.send(
            json.dumps(make_message("subscribe", {"channel": "chat"}))
        )
        await ws.send(
            json.dumps(make_message("subscribe", {"channel": "system"}))
        )
        await asyncio.sleep(0.05)
        assert server.registry.channels() == {"chat": 1, "system": 1}
        assert cid in server.registry.channel_subscribers("chat")
        assert cid in server.registry.channel_subscribers("system")


async def test_unsubscribe_stops_delivery(client, server):
    subscriber, _ = client
    async with websockets.connect(server.ws_url) as sender:
        await sender.recv()
        await subscriber.send(
            json.dumps(make_message("subscribe", {"channel": "alerts"}))
        )
        await asyncio.sleep(0.05)
        await sender.send(
            json.dumps(make_message("broadcast", {"channel": "alerts", "n": 1}))
        )
        assert (await asyncio.wait_for(subscriber.recv(), timeout=3)) is not None

        await subscriber.send(
            json.dumps(make_message("unsubscribe", {"channel": "alerts"}))
        )
        await asyncio.sleep(0.05)
        await sender.send(
            json.dumps(make_message("broadcast", {"channel": "alerts", "n": 2}))
        )
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(subscriber.recv(), timeout=0.3)


async def test_subscribe_missing_channel_returns_error(client):
    ws, _ = client
    await ws.send(json.dumps(make_message("subscribe", {})))
    msg = parse(await asyncio.wait_for(ws.recv(), timeout=3))
    assert msg["type"] == "system"
    assert msg["payload"]["event"] == "error"


async def test_disconnect_cleans_up_channel(client, server):
    ws, _ = client
    await ws.send(json.dumps(make_message("subscribe", {"channel": "alerts"})))
    await asyncio.sleep(0.05)
    assert server.registry.channels() == {"alerts": 1}
    await ws.close()
    await asyncio.sleep(0.2)
    assert server.registry.channels() == {}


# ── REST endpoints ─────────────────────────────────────────────────

async def test_get_channels_lists_counts(client, server):
    ws, _ = client
    await ws.send(json.dumps(make_message("subscribe", {"channel": "alerts"})))
    await ws.send(json.dumps(make_message("subscribe", {"channel": "chat"})))
    await asyncio.sleep(0.05)

    data = await http_get(server.http_url + "/channels")
    assert data["channels"] == {"alerts": 1, "chat": 1}


async def test_get_channel_subscribers(client, server):
    sub, sub_id = client
    await sub.send(json.dumps(make_message("subscribe", {"channel": "alerts"})))
    await asyncio.sleep(0.05)

    data = await http_get(server.http_url + "/channels/alerts/subscribers")
    assert data["channel"] == "alerts"
    assert data["subscribers"] == [sub_id]


async def test_get_channel_subscribers_unknown_channel(client, server):
    data = await http_get(server.http_url + "/channels/void/subscribers")
    assert data["channel"] == "void"
    assert data["subscribers"] == []
