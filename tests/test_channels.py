import asyncio
import json

import pytest
import websockets
from aiohttp.test_utils import TestClient, TestServer

from notification_server.registry import ClientRegistry
from notification_server.soap import create_soap_app
from notification_server.ws_server import NotificationServer


# ── Registry-level channel subscription tests ───────────────────────────


def test_subscribe_adds_client_to_channel():
    registry = ClientRegistry()
    registry.add("a", "conn-a")
    registry.subscribe("a", "alerts")
    assert registry.channel_subscribers("alerts") == ["a"]
    assert registry.channels() == {"alerts": 1}


def test_multiple_clients_can_subscribe_to_same_channel():
    registry = ClientRegistry()
    registry.add("a", "conn-a")
    registry.add("b", "conn-b")
    registry.subscribe("a", "alerts")
    registry.subscribe("b", "alerts")
    assert registry.channel_subscribers("alerts") == ["a", "b"]
    assert registry.channels() == {"alerts": 2}


def test_client_can_subscribe_to_multiple_channels():
    registry = ClientRegistry()
    registry.add("a", "conn-a")
    registry.subscribe("a", "alerts")
    registry.subscribe("a", "chat")
    assert registry.channels() == {"alerts": 1, "chat": 1}


def test_unsubscribe_removes_client_from_channel():
    registry = ClientRegistry()
    registry.add("a", "conn-a")
    registry.subscribe("a", "alerts")
    registry.unsubscribe("a", "alerts")
    assert registry.channel_subscribers("alerts") == []
    assert registry.channels() == {}


def test_unsubscribe_unknown_channel_is_a_no_op():
    registry = ClientRegistry()
    registry.add("a", "conn-a")
    registry.unsubscribe("a", "does-not-exist")
    assert registry.channels() == {}


def test_remove_client_cleans_up_subscriptions():
    registry = ClientRegistry()
    registry.add("a", "conn-a")
    registry.add("b", "conn-b")
    registry.subscribe("a", "alerts")
    registry.subscribe("b", "alerts")
    registry.remove("a")
    assert registry.channel_subscribers("alerts") == ["b"]
    assert registry.channels() == {"alerts": 1}


def test_connections_for_channel_returns_live_connections():
    registry = ClientRegistry()
    registry.add("a", "conn-a")
    registry.add("b", "conn-b")
    registry.subscribe("a", "alerts")
    registry.subscribe("b", "chat")
    assert registry.connections_for_channel("alerts") == ["conn-a"]


def test_connections_for_channel_unknown_channel_is_empty():
    registry = ClientRegistry()
    assert registry.connections_for_channel("nope") == []


# ── WebSocket-level subscribe/unsubscribe/routing tests ─────────────────


@pytest.fixture
async def running_server():
    server_wrapper = NotificationServer()
    ws_server = await server_wrapper.serve("localhost", 0)
    port = ws_server.sockets[0].getsockname()[1]
    yield server_wrapper, f"ws://localhost:{port}"
    ws_server.close()
    await ws_server.wait_closed()


async def _subscribe(ws, channel):
    await ws.send(json.dumps({"type": "subscribe", "channel": channel, "payload": {}}))
    return json.loads(await ws.recv())


async def _unsubscribe(ws, channel):
    await ws.send(json.dumps({"type": "unsubscribe", "channel": channel, "payload": {}}))
    return json.loads(await ws.recv())


async def test_subscribe_confirms_via_system_message(running_server):
    server, uri = running_server
    async with websockets.connect(uri) as ws:
        await ws.recv()
        ack = await _subscribe(ws, "alerts")
        assert ack["type"] == "system"
        assert ack["payload"]["event"] == "subscribed"
        assert ack["payload"]["channel"] == "alerts"


async def test_subscribe_without_channel_gets_error(running_server):
    server, uri = running_server
    async with websockets.connect(uri) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "subscribe", "payload": {}}))
        err = json.loads(await ws.recv())
        assert err["type"] == "system"
        assert err["payload"]["event"] == "error"


async def test_channel_broadcast_reaches_only_subscribers(running_server):
    server, uri = running_server
    async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2, websockets.connect(
        uri
    ) as ws3:
        await ws1.recv()
        await ws2.recv()
        await ws3.recv()

        await _subscribe(ws1, "alerts")
        await _subscribe(ws2, "alerts")
        # ws3 does not subscribe

        await ws1.send(
            json.dumps(
                {
                    "type": "broadcast",
                    "channel": "alerts",
                    "payload": {"text": "fire!"},
                    "timestamp": "2026-08-13T00:00:00Z",
                }
            )
        )

        got1 = json.loads(await ws1.recv())
        got2 = json.loads(await ws2.recv())
        assert got1["payload"]["text"] == "fire!"
        assert got1["channel"] == "alerts"
        assert got2["payload"]["text"] == "fire!"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws3.recv(), timeout=0.2)


async def test_unsubscribed_client_stops_receiving_channel_messages(running_server):
    server, uri = running_server
    async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
        await ws1.recv()
        await ws2.recv()

        await _subscribe(ws1, "alerts")
        await _subscribe(ws2, "alerts")
        await _unsubscribe(ws2, "alerts")

        await ws1.send(
            json.dumps(
                {
                    "type": "broadcast",
                    "channel": "alerts",
                    "payload": {"text": "still here"},
                    "timestamp": "2026-08-13T00:00:00Z",
                }
            )
        )

        got1 = json.loads(await ws1.recv())
        assert got1["payload"]["text"] == "still here"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws2.recv(), timeout=0.2)


async def test_broadcast_without_channel_still_reaches_everyone(running_server):
    server, uri = running_server
    async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
        await ws1.recv()
        await ws2.recv()

        await _subscribe(ws1, "alerts")
        # ws2 subscribes to nothing

        await ws1.send(
            json.dumps(
                {
                    "type": "broadcast",
                    "payload": {"text": "global"},
                    "timestamp": "2026-08-13T00:00:00Z",
                }
            )
        )

        got1 = json.loads(await ws1.recv())
        got2 = json.loads(await ws2.recv())
        assert got1["payload"]["text"] == "global"
        assert got2["payload"]["text"] == "global"


async def test_channel_broadcast_to_channel_with_no_subscribers_is_a_no_op(running_server):
    server, uri = running_server
    async with websockets.connect(uri) as ws1:
        await ws1.recv()
        await ws1.send(
            json.dumps(
                {
                    "type": "broadcast",
                    "channel": "empty-channel",
                    "payload": {"text": "anyone?"},
                    "timestamp": "2026-08-13T00:00:00Z",
                }
            )
        )
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws1.recv(), timeout=0.2)


async def test_disconnect_cleans_up_channel_subscription(running_server):
    server, uri = running_server
    ws1 = await websockets.connect(uri)
    await ws1.recv()
    await _subscribe(ws1, "alerts")
    assert server.registry.channels() == {"alerts": 1}
    await ws1.close()
    await asyncio.sleep(0.2)
    assert server.registry.channels() == {}


# ── REST endpoint tests ───────────────────────────────────────────────


@pytest.fixture
async def rest_client():
    registry = ClientRegistry()
    app = create_soap_app(registry)
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    yield client, registry
    await client.close()


async def test_list_channels_empty(rest_client):
    client, _registry = rest_client
    resp = await client.get("/channels")
    assert resp.status == 200
    body = await resp.json()
    assert body == {"channels": []}


async def test_list_channels_reflects_subscriptions(rest_client):
    client, registry = rest_client
    registry.add("a", object())
    registry.add("b", object())
    registry.subscribe("a", "alerts")
    registry.subscribe("b", "alerts")
    registry.subscribe("a", "chat")

    resp = await client.get("/channels")
    body = await resp.json()
    assert body == {
        "channels": [
            {"name": "alerts", "subscribers": 2},
            {"name": "chat", "subscribers": 1},
        ]
    }


async def test_channel_subscribers_endpoint(rest_client):
    client, registry = rest_client
    registry.add("a", object())
    registry.add("b", object())
    registry.subscribe("a", "alerts")
    registry.subscribe("b", "alerts")

    resp = await client.get("/channels/alerts/subscribers")
    assert resp.status == 200
    body = await resp.json()
    assert body == {"channel": "alerts", "subscribers": ["a", "b"]}


async def test_channel_subscribers_endpoint_unknown_channel(rest_client):
    client, _registry = rest_client
    resp = await client.get("/channels/nope/subscribers")
    assert resp.status == 200
    body = await resp.json()
    assert body == {"channel": "nope", "subscribers": []}
