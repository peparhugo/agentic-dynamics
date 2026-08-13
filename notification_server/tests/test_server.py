import asyncio
import json
import urllib.request

import pytest
import websockets

from notification_server.server import NotificationServer


def ws_uri(srv: NotificationServer) -> str:
    return f"ws://localhost:{srv.bound_port}"


def health_url(srv: NotificationServer) -> str:
    return f"http://localhost:{srv.bound_port}/health"


async def get_health(srv: NotificationServer) -> dict:
    def _fetch():
        with urllib.request.urlopen(health_url(srv)) as resp:
            return resp.status, json.loads(resp.read())

    return await asyncio.to_thread(_fetch)


def channels_url(srv: NotificationServer) -> str:
    return f"http://localhost:{srv.bound_port}/channels"


def subscribers_url(srv: NotificationServer, channel: str) -> str:
    return f"http://localhost:{srv.bound_port}/channels/{channel}/subscribers"


async def get_json(url: str) -> tuple[int, dict]:
    def _fetch():
        with urllib.request.urlopen(url) as resp:
            return resp.status, json.loads(resp.read())

    return await asyncio.to_thread(_fetch)


async def subscribe(ws, channel: str) -> dict:
    await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": channel}}))
    return await recv_json(ws)


async def unsubscribe(ws, channel: str) -> dict:
    await ws.send(json.dumps({"type": "unsubscribe", "payload": {"channel": channel}}))
    return await recv_json(ws)


async def recv_json(websocket) -> dict:
    return json.loads(await websocket.recv())


async def wait_until(predicate, timeout: float = 2.0, interval: float = 0.02) -> None:
    async def _loop():
        while not predicate():
            await asyncio.sleep(interval)

    await asyncio.wait_for(_loop(), timeout=timeout)


# -- connection lifecycle -------------------------------------------------


@pytest.mark.asyncio
async def test_client_receives_unique_id_on_connect(server):
    async with websockets.connect(ws_uri(server)) as ws1, websockets.connect(ws_uri(server)) as ws2:
        welcome1 = await recv_json(ws1)
        welcome2 = await recv_json(ws2)

        assert welcome1["type"] == "system"
        assert welcome2["type"] == "system"
        id1 = welcome1["payload"]["client_id"]
        id2 = welcome2["payload"]["client_id"]

        assert id1 != id2
        assert server.registry.count() == 2


@pytest.mark.asyncio
async def test_disconnect_removes_client_from_registry(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        assert server.registry.count() == 1

    await wait_until(lambda: server.registry.count() == 0)


# -- health endpoint --------------------------------------------------------


@pytest.mark.asyncio
async def test_health_endpoint_with_no_clients(server):
    status, body = await get_health(server)
    assert status == 200
    assert body == {"connected_clients": 0}


@pytest.mark.asyncio
async def test_health_endpoint_reflects_connected_clients(server):
    async with websockets.connect(ws_uri(server)) as ws1:
        await recv_json(ws1)
        async with websockets.connect(ws_uri(server)) as ws2:
            await recv_json(ws2)
            status, body = await get_health(server)
            assert status == 200
            assert body == {"connected_clients": 2}

    await wait_until(lambda: server.registry.count() == 0)
    status, body = await get_health(server)
    assert body == {"connected_clients": 0}


# -- broadcast ----------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcast_reaches_all_connected_clients(server):
    async with websockets.connect(ws_uri(server)) as ws1, websockets.connect(ws_uri(server)) as ws2, \
            websockets.connect(ws_uri(server)) as ws3:
        for ws in (ws1, ws2, ws3):
            await recv_json(ws)

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "hello everyone"},
            "timestamp": "2024-01-01T00:00:00Z",
        }))

        for ws in (ws1, ws2, ws3):
            message = await recv_json(ws)
            assert message["type"] == "broadcast"
            assert message["payload"] == {"text": "hello everyone"}


# -- direct messages ------------------------------------------------------


@pytest.mark.asyncio
async def test_direct_message_delivered_only_to_target(server):
    async with websockets.connect(ws_uri(server)) as ws1, websockets.connect(ws_uri(server)) as ws2, \
            websockets.connect(ws_uri(server)) as ws3:
        welcome1 = await recv_json(ws1)
        welcome2 = await recv_json(ws2)
        await recv_json(ws3)

        target_id = welcome2["payload"]["client_id"]

        await ws1.send(json.dumps({
            "type": "direct",
            "payload": {"target_id": target_id, "text": "hi there"},
            "timestamp": "2024-01-01T00:00:00Z",
        }))

        message = await recv_json(ws2)
        assert message["type"] == "direct"
        assert message["payload"]["text"] == "hi there"
        assert message["sender_id"] == welcome1["payload"]["client_id"]

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws3.recv(), timeout=0.2)


@pytest.mark.asyncio
async def test_direct_message_to_unknown_target_returns_error(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        await ws.send(json.dumps({
            "type": "direct",
            "payload": {"target_id": "does-not-exist", "text": "hi"},
            "timestamp": "2024-01-01T00:00:00Z",
        }))
        message = await recv_json(ws)
        assert message["type"] == "system"
        assert "error" in message["payload"]


# -- message validation -----------------------------------------------------


@pytest.mark.asyncio
async def test_system_message_from_client_is_rejected(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        await ws.send(json.dumps({
            "type": "system",
            "payload": {"anything": "here"},
            "timestamp": "2024-01-01T00:00:00Z",
        }))
        message = await recv_json(ws)
        assert message["type"] == "system"
        assert "error" in message["payload"]


@pytest.mark.asyncio
async def test_unknown_message_type_returns_error(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        await ws.send(json.dumps({
            "type": "bogus",
            "payload": {},
            "timestamp": "2024-01-01T00:00:00Z",
        }))
        message = await recv_json(ws)
        assert message["type"] == "system"
        assert "error" in message["payload"]


@pytest.mark.asyncio
async def test_invalid_json_returns_error(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        await ws.send("not valid json")
        message = await recv_json(ws)
        assert message["type"] == "system"
        assert "error" in message["payload"]


@pytest.mark.asyncio
async def test_message_missing_required_fields_returns_error(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        await ws.send(json.dumps({"type": "broadcast"}))
        message = await recv_json(ws)
        assert message["type"] == "system"
        assert "error" in message["payload"]


# -- message envelope ---------------------------------------------------------


@pytest.mark.asyncio
async def test_all_messages_have_required_envelope_fields(server):
    async with websockets.connect(ws_uri(server)) as ws:
        welcome = await recv_json(ws)
        assert set(["type", "payload", "timestamp"]).issubset(welcome.keys())
        assert welcome["type"] in {"broadcast", "direct", "system"}


# -- channel subscriptions ---------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_confirms_with_system_message(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        ack = await subscribe(ws, "alerts")
        assert ack["type"] == "system"
        assert ack["payload"] == {"event": "subscribed", "channel": "alerts"}


@pytest.mark.asyncio
async def test_unsubscribe_confirms_with_system_message(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        await subscribe(ws, "alerts")
        ack = await unsubscribe(ws, "alerts")
        assert ack["type"] == "system"
        assert ack["payload"] == {"event": "unsubscribed", "channel": "alerts"}


@pytest.mark.asyncio
async def test_subscribe_missing_channel_returns_error(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        await ws.send(json.dumps({"type": "subscribe", "payload": {}}))
        message = await recv_json(ws)
        assert message["type"] == "system"
        assert "error" in message["payload"]


@pytest.mark.asyncio
async def test_channel_message_delivered_only_to_subscribers(server):
    async with websockets.connect(ws_uri(server)) as ws1, websockets.connect(ws_uri(server)) as ws2, \
            websockets.connect(ws_uri(server)) as ws3:
        for ws in (ws1, ws2, ws3):
            await recv_json(ws)

        await subscribe(ws1, "alerts")
        await subscribe(ws2, "alerts")
        # ws3 stays unsubscribed

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"channel": "alerts", "text": "fire drill"},
        }))

        for ws in (ws1, ws2):
            message = await recv_json(ws)
            assert message["type"] == "broadcast"
            assert message["payload"]["text"] == "fire drill"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws3.recv(), timeout=0.2)


@pytest.mark.asyncio
async def test_channel_less_broadcast_still_reaches_everyone(server):
    async with websockets.connect(ws_uri(server)) as ws1, websockets.connect(ws_uri(server)) as ws2:
        await recv_json(ws1)
        await recv_json(ws2)

        await subscribe(ws1, "alerts")
        # ws2 never subscribes to anything

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "no channel here"},
        }))

        for ws in (ws1, ws2):
            message = await recv_json(ws)
            assert message["payload"]["text"] == "no channel here"


@pytest.mark.asyncio
async def test_client_can_subscribe_to_multiple_channels(server):
    async with websockets.connect(ws_uri(server)) as ws1, websockets.connect(ws_uri(server)) as ws2:
        await recv_json(ws1)
        await recv_json(ws2)

        await subscribe(ws1, "alerts")
        await subscribe(ws1, "chat")
        await subscribe(ws2, "chat")

        await ws2.send(json.dumps({
            "type": "broadcast",
            "payload": {"channel": "alerts", "text": "should not reach ws2"},
        }))
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws2.recv(), timeout=0.2)

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"channel": "chat", "text": "hi chat"},
        }))
        message = await recv_json(ws2)
        assert message["payload"]["text"] == "hi chat"


@pytest.mark.asyncio
async def test_unsubscribed_client_stops_receiving_channel_messages(server):
    async with websockets.connect(ws_uri(server)) as ws1, websockets.connect(ws_uri(server)) as ws2:
        await recv_json(ws1)
        await recv_json(ws2)

        await subscribe(ws1, "alerts")
        await subscribe(ws2, "alerts")
        await unsubscribe(ws2, "alerts")

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"channel": "alerts", "text": "still here"},
        }))
        message = await recv_json(ws1)
        assert message["payload"]["text"] == "still here"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws2.recv(), timeout=0.2)


@pytest.mark.asyncio
async def test_disconnecting_client_is_removed_from_channel_subscriptions(server):
    async with websockets.connect(ws_uri(server)) as ws1:
        await recv_json(ws1)
        await subscribe(ws1, "alerts")

    await wait_until(lambda: server.registry.count() == 0)
    status, body = await get_json(channels_url(server))
    assert status == 200
    assert body["channels"] == {}


# -- channel REST endpoints ---------------------------------------------------


@pytest.mark.asyncio
async def test_channels_endpoint_lists_active_channels_and_counts(server):
    status, body = await get_json(channels_url(server))
    assert status == 200
    assert body == {"channels": {}}

    async with websockets.connect(ws_uri(server)) as ws1, websockets.connect(ws_uri(server)) as ws2:
        await recv_json(ws1)
        await recv_json(ws2)
        await subscribe(ws1, "alerts")
        await subscribe(ws2, "alerts")
        await subscribe(ws2, "chat")

        status, body = await get_json(channels_url(server))
        assert status == 200
        assert body == {"channels": {"alerts": 2, "chat": 1}}


@pytest.mark.asyncio
async def test_channel_subscribers_endpoint_lists_subscriber_ids(server):
    async with websockets.connect(ws_uri(server)) as ws1, websockets.connect(ws_uri(server)) as ws2:
        welcome1 = await recv_json(ws1)
        welcome2 = await recv_json(ws2)
        await subscribe(ws1, "alerts")
        await subscribe(ws2, "alerts")

        status, body = await get_json(subscribers_url(server, "alerts"))
        assert status == 200
        assert body["channel"] == "alerts"
        assert sorted(body["subscribers"]) == sorted(
            [welcome1["payload"]["client_id"], welcome2["payload"]["client_id"]]
        )


@pytest.mark.asyncio
async def test_channel_subscribers_endpoint_returns_empty_for_unknown_channel(server):
    status, body = await get_json(subscribers_url(server, "ghost-channel"))
    assert status == 200
    assert body == {"channel": "ghost-channel", "subscribers": []}


@pytest.mark.asyncio
async def test_existing_health_endpoint_still_works_alongside_channels(server):
    status, body = await get_health(server)
    assert status == 200
    assert body == {"connected_clients": 0}
