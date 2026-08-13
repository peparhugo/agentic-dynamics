import asyncio
import json
import urllib.request

import pytest
import websockets
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from notification_server import (
    MESSAGE_TYPES,
    ChannelRegistry,
    ClientRegistry,
    NotificationServer,
    make_message,
)


# ── unit tests: message helpers & registry ──────────────────────────────


def test_make_message_shape():
    msg = make_message("broadcast", {"text": "hi"})
    assert msg["type"] == "broadcast"
    assert msg["payload"] == {"text": "hi"}
    assert "timestamp" in msg and isinstance(msg["timestamp"], str)


def test_make_message_rejects_unsupported_type():
    with pytest.raises(ValueError):
        make_message("not-a-type", {})


def test_supported_types_contains_expected():
    assert MESSAGE_TYPES == {"broadcast", "direct", "system", "subscribe", "unsubscribe"}


class FakeConnection:
    def __init__(self):
        self.sent = []
        self.closed = False

    async def send(self, message):
        if self.closed:
            raise websockets.exceptions.ConnectionClosed(None, None)
        self.sent.append(message)


@pytest.mark.asyncio
async def test_registry_add_assigns_unique_ids():
    registry = ClientRegistry()
    id_a = await registry.add(FakeConnection())
    id_b = await registry.add(FakeConnection())
    assert id_a != id_b
    assert await registry.count() == 2


@pytest.mark.asyncio
async def test_registry_remove():
    registry = ClientRegistry()
    client_id = await registry.add(FakeConnection())
    assert await registry.count() == 1
    await registry.remove(client_id)
    assert await registry.count() == 0


@pytest.mark.asyncio
async def test_registry_remove_unknown_is_noop():
    registry = ClientRegistry()
    await registry.remove("does-not-exist")
    assert await registry.count() == 0


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_and_skips_closed():
    app = NotificationServer()
    conn_a = FakeConnection()
    conn_b = FakeConnection()
    conn_b.closed = True
    id_a = await app.registry.add(conn_a)
    id_b = await app.registry.add(conn_b)

    sent = await app.broadcast({"text": "hello"})

    assert sent == 1
    assert len(conn_a.sent) == 1
    body = json.loads(conn_a.sent[0])
    assert body["type"] == "broadcast"
    assert body["payload"] == {"text": "hello"}
    # the closed connection should have been pruned from the registry
    assert await app.registry.get(id_b) is None
    assert await app.registry.get(id_a) is not None


@pytest.mark.asyncio
async def test_send_direct_to_unknown_client_returns_false():
    app = NotificationServer()
    delivered = await app.send_direct("unknown-id", {"text": "hi"})
    assert delivered is False


# ── unit tests: channel registry ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_channel_registry_subscribe_and_counts():
    channels = ChannelRegistry()
    await channels.subscribe("client-a", "alerts")
    await channels.subscribe("client-b", "alerts")
    await channels.subscribe("client-a", "chat")
    assert await channels.channel_counts() == {"alerts": 2, "chat": 1}
    assert await channels.subscribers("alerts") == ["client-a", "client-b"]


@pytest.mark.asyncio
async def test_channel_registry_unsubscribe_removes_empty_channel():
    channels = ChannelRegistry()
    await channels.subscribe("client-a", "alerts")
    await channels.unsubscribe("client-a", "alerts")
    assert await channels.channel_counts() == {}
    assert await channels.subscribers("alerts") == []


@pytest.mark.asyncio
async def test_channel_registry_unsubscribe_unknown_is_noop():
    channels = ChannelRegistry()
    await channels.unsubscribe("client-a", "does-not-exist")
    assert await channels.channel_counts() == {}


@pytest.mark.asyncio
async def test_channel_registry_remove_client_prunes_all_channels():
    channels = ChannelRegistry()
    await channels.subscribe("client-a", "alerts")
    await channels.subscribe("client-a", "chat")
    await channels.subscribe("client-b", "chat")
    await channels.remove_client("client-a")
    assert await channels.channel_counts() == {"chat": 1}
    assert await channels.subscribers("chat") == ["client-b"]


@pytest.mark.asyncio
async def test_broadcast_with_channel_only_reaches_subscribers():
    app = NotificationServer()
    conn_a = FakeConnection()
    conn_b = FakeConnection()
    id_a = await app.registry.add(conn_a)
    await app.registry.add(conn_b)
    await app.channels.subscribe(id_a, "alerts")

    sent = await app.broadcast({"text": "fire"}, channel="alerts")

    assert sent == 1
    assert len(conn_a.sent) == 1
    assert len(conn_b.sent) == 0
    body = json.loads(conn_a.sent[0])
    assert body["channel"] == "alerts"


# ── integration tests: real server over a real socket ───────────────────


@pytest.fixture
async def running_server():
    app = NotificationServer()
    async with serve(app.handler, "localhost", 0, process_request=app.process_request) as server:
        port = server.sockets[0].getsockname()[1]
        yield app, f"ws://localhost:{port}"


async def _recv_json(ws):
    return json.loads(await ws.recv())


@pytest.mark.asyncio
async def test_connect_assigns_unique_id_via_system_message(running_server):
    app, uri = running_server
    async with connect(uri) as ws:
        welcome = await _recv_json(ws)
        assert welcome["type"] == "system"
        assert welcome["payload"]["event"] == "connected"
        assert "client_id" in welcome["payload"]
        assert await app.registry.count() == 1


@pytest.mark.asyncio
async def test_two_clients_get_distinct_ids(running_server):
    app, uri = running_server
    async with connect(uri) as ws1, connect(uri) as ws2:
        w1 = await _recv_json(ws1)
        w2 = await _recv_json(ws2)
        assert w1["payload"]["client_id"] != w2["payload"]["client_id"]
        assert await app.registry.count() == 2


@pytest.mark.asyncio
async def test_broadcast_reaches_all_connected_clients(running_server):
    app, uri = running_server
    async with connect(uri) as ws1, connect(uri) as ws2:
        await _recv_json(ws1)  # welcome
        await _recv_json(ws2)  # welcome

        await ws1.send(json.dumps({"type": "broadcast", "payload": {"text": "hello all"}}))

        msg1 = await _recv_json(ws1)
        msg2 = await _recv_json(ws2)
        assert msg1["type"] == "broadcast"
        assert msg1["payload"] == {"text": "hello all"}
        assert msg2 == msg1


@pytest.mark.asyncio
async def test_disconnect_removes_client_cleanly(running_server):
    app, uri = running_server
    ws = await connect(uri)
    await _recv_json(ws)
    assert await app.registry.count() == 1
    await ws.close()

    # give the server loop a moment to notice the close
    for _ in range(50):
        if await app.registry.count() == 0:
            break
        import asyncio

        await asyncio.sleep(0.02)

    assert await app.registry.count() == 0


@pytest.mark.asyncio
async def test_direct_message_delivered_only_to_target(running_server):
    app, uri = running_server
    async with connect(uri) as ws1, connect(uri) as ws2:
        w1 = await _recv_json(ws1)
        await _recv_json(ws2)
        target_id = w1["payload"]["client_id"]

        await ws2.send(
            json.dumps(
                {
                    "type": "direct",
                    "payload": {"client_id": target_id, "payload": {"text": "just for you"}},
                }
            )
        )

        got = await _recv_json(ws1)
        assert got["type"] == "direct"
        assert got["payload"] == {"text": "just for you"}


@pytest.mark.asyncio
async def test_invalid_json_yields_system_error(running_server):
    app, uri = running_server
    async with connect(uri) as ws:
        await _recv_json(ws)  # welcome
        await ws.send("not json")
        err = await _recv_json(ws)
        assert err["type"] == "system"
        assert err["payload"]["event"] == "error"


@pytest.mark.asyncio
async def test_unsupported_message_type_yields_system_error(running_server):
    app, uri = running_server
    async with connect(uri) as ws:
        await _recv_json(ws)  # welcome
        await ws.send(json.dumps({"type": "bogus", "payload": {}}))
        err = await _recv_json(ws)
        assert err["type"] == "system"
        assert err["payload"]["event"] == "error"


@pytest.mark.asyncio
async def test_health_endpoint_reports_connected_count(running_server):
    import asyncio
    import urllib.request

    app, uri = running_server
    http_uri = uri.replace("ws://", "http://") + "/health"

    def fetch():
        with urllib.request.urlopen(http_uri) as resp:
            return resp.status, json.loads(resp.read())

    async with connect(uri):
        status, data = await asyncio.to_thread(fetch)
        assert status == 200
        assert data["connected_clients"] == 1


# ── integration tests: channel subscriptions ─────────────────────────────


@pytest.mark.asyncio
async def test_subscribe_yields_ack_and_registers_client(running_server):
    app, uri = running_server
    async with connect(uri) as ws:
        await _recv_json(ws)  # welcome

        await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        ack = await _recv_json(ws)
        assert ack["type"] == "system"
        assert ack["payload"]["event"] == "subscribed"
        assert ack["payload"]["channel"] == "alerts"
        assert await app.channels.channel_counts() == {"alerts": 1}


@pytest.mark.asyncio
async def test_subscribe_without_channel_yields_error(running_server):
    app, uri = running_server
    async with connect(uri) as ws:
        await _recv_json(ws)  # welcome
        await ws.send(json.dumps({"type": "subscribe", "payload": {}}))
        err = await _recv_json(ws)
        assert err["type"] == "system"
        assert err["payload"]["event"] == "error"


@pytest.mark.asyncio
async def test_unsubscribe_removes_client_from_channel(running_server):
    app, uri = running_server
    async with connect(uri) as ws:
        await _recv_json(ws)  # welcome
        await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await _recv_json(ws)  # subscribed ack

        await ws.send(json.dumps({"type": "unsubscribe", "channel": "alerts"}))
        ack = await _recv_json(ws)
        assert ack["payload"]["event"] == "unsubscribed"
        assert await app.channels.channel_counts() == {}


@pytest.mark.asyncio
async def test_channel_message_delivered_only_to_subscribers(running_server):
    app, uri = running_server
    async with connect(uri) as ws1, connect(uri) as ws2, connect(uri) as ws3:
        await _recv_json(ws1)  # welcome
        await _recv_json(ws2)  # welcome
        await _recv_json(ws3)  # welcome

        await ws1.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await _recv_json(ws1)  # ack
        await ws2.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await _recv_json(ws2)  # ack
        # ws3 stays unsubscribed

        await ws1.send(
            json.dumps(
                {"type": "broadcast", "channel": "alerts", "payload": {"text": "fire"}}
            )
        )

        msg1 = await _recv_json(ws1)
        msg2 = await _recv_json(ws2)
        assert msg1["payload"] == {"text": "fire"}
        assert msg1["channel"] == "alerts"
        assert msg2 == msg1

        # ws3 should receive nothing on the channel — confirm by sending a
        # plain, channel-less broadcast that ws3 *should* receive instead.
        await ws1.send(json.dumps({"type": "broadcast", "payload": {"text": "everyone"}}))
        everyone1 = await _recv_json(ws1)
        everyone2 = await _recv_json(ws2)
        everyone3 = await _recv_json(ws3)
        assert everyone1["payload"] == {"text": "everyone"}
        assert everyone2 == everyone1
        assert everyone3 == everyone1


@pytest.mark.asyncio
async def test_multiple_channel_subscriptions_per_client(running_server):
    app, uri = running_server
    async with connect(uri) as ws:
        client_id = (await _recv_json(ws))["payload"]["client_id"]
        await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await _recv_json(ws)
        await ws.send(json.dumps({"type": "subscribe", "channel": "chat"}))
        await _recv_json(ws)

        counts = await app.channels.channel_counts()
        assert counts == {"alerts": 1, "chat": 1}
        assert await app.channels.subscribers("alerts") == [client_id]
        assert await app.channels.subscribers("chat") == [client_id]


@pytest.mark.asyncio
async def test_disconnect_prunes_channel_subscriptions(running_server):
    app, uri = running_server
    ws = await connect(uri)
    await _recv_json(ws)
    await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
    await _recv_json(ws)
    assert await app.channels.channel_counts() == {"alerts": 1}

    await ws.close()

    for _ in range(50):
        if await app.channels.channel_counts() == {}:
            break
        await asyncio.sleep(0.02)

    assert await app.channels.channel_counts() == {}


@pytest.mark.asyncio
async def test_channels_endpoint_lists_active_channels_and_counts(running_server):
    app, uri = running_server
    http_uri = uri.replace("ws://", "http://") + "/channels"

    def fetch():
        with urllib.request.urlopen(http_uri) as resp:
            return resp.status, json.loads(resp.read())

    async with connect(uri) as ws1, connect(uri) as ws2:
        await _recv_json(ws1)
        await _recv_json(ws2)
        await ws1.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await _recv_json(ws1)
        await ws2.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await _recv_json(ws2)
        await ws1.send(json.dumps({"type": "subscribe", "channel": "chat"}))
        await _recv_json(ws1)

        status, data = await asyncio.to_thread(fetch)
        assert status == 200
        assert data["channels"] == {"alerts": 2, "chat": 1}


@pytest.mark.asyncio
async def test_channel_subscribers_endpoint_lists_subscriber_ids(running_server):
    app, uri = running_server

    async with connect(uri) as ws1, connect(uri) as ws2:
        w1 = await _recv_json(ws1)
        await _recv_json(ws2)
        client_id = w1["payload"]["client_id"]

        await ws1.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
        await _recv_json(ws1)

        http_uri = uri.replace("ws://", "http://") + "/channels/alerts/subscribers"

        def fetch():
            with urllib.request.urlopen(http_uri) as resp:
                return resp.status, json.loads(resp.read())

        status, data = await asyncio.to_thread(fetch)
        assert status == 200
        assert data["channel"] == "alerts"
        assert data["subscribers"] == [client_id]


@pytest.mark.asyncio
async def test_channel_subscribers_endpoint_empty_for_unknown_channel(running_server):
    app, uri = running_server
    http_uri = uri.replace("ws://", "http://") + "/channels/does-not-exist/subscribers"

    def fetch():
        with urllib.request.urlopen(http_uri) as resp:
            return resp.status, json.loads(resp.read())

    async with connect(uri):
        status, data = await asyncio.to_thread(fetch)
        assert status == 200
        assert data["channel"] == "does-not-exist"
        assert data["subscribers"] == []
