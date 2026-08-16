import asyncio
import json

import fakeredis
import pytest
import websockets
from fakeredis import aioredis as fakeredis_aioredis
from websockets.asyncio.client import connect

from notification_server import (
    DATABASE_URL,
    REDIS_URL,
    ChannelRegistry,
    Client,
    ClientRegistry,
    NotificationServer,
    create_server,
    make_message,
)
from persistence import MessageStore
from redis_backbone import RedisBackbone


# ── Unit tests: ClientRegistry / make_message ─────────────────────

def test_registry_add_and_count():
    registry = ClientRegistry()
    registry.add(Client(client_id="a", connection=object()))
    registry.add(Client(client_id="b", connection=object()))
    assert registry.count() == 2


def test_registry_remove():
    registry = ClientRegistry()
    registry.add(Client(client_id="a", connection=object()))
    registry.remove("a")
    assert registry.count() == 0
    assert registry.get("a") is None


def test_registry_remove_missing_is_noop():
    registry = ClientRegistry()
    registry.remove("does-not-exist")
    assert registry.count() == 0


def test_registry_ids_are_unique_per_add():
    registry = ClientRegistry()
    ids = set()
    for i in range(50):
        cid = f"client-{i}"
        registry.add(Client(client_id=cid, connection=object()))
        ids.add(cid)
    assert registry.count() == 50
    assert len(ids) == 50


def test_make_message_valid_types():
    for t in ("broadcast", "direct", "system"):
        msg = make_message(t, {"foo": "bar"})
        assert msg["type"] == t
        assert msg["payload"] == {"foo": "bar"}
        assert "timestamp" in msg


def test_make_message_rejects_unsupported_type():
    with pytest.raises(ValueError):
        make_message("not-a-type", {})


# ── Unit tests: ChannelRegistry ────────────────────────────────────

def test_channel_subscribe_and_subscribers():
    registry = ChannelRegistry()
    registry.subscribe("alerts", "c1")
    registry.subscribe("alerts", "c2")
    assert registry.subscribers("alerts") == ["c1", "c2"]


def test_channel_subscribe_is_idempotent():
    registry = ChannelRegistry()
    registry.subscribe("alerts", "c1")
    registry.subscribe("alerts", "c1")
    assert registry.subscribers("alerts") == ["c1"]


def test_channel_client_can_join_multiple_channels():
    registry = ChannelRegistry()
    registry.subscribe("alerts", "c1")
    registry.subscribe("chat", "c1")
    assert registry.channels() == {"alerts": 1, "chat": 1}


def test_channel_unsubscribe_removes_client():
    registry = ChannelRegistry()
    registry.subscribe("alerts", "c1")
    registry.subscribe("alerts", "c2")
    registry.unsubscribe("alerts", "c1")
    assert registry.subscribers("alerts") == ["c2"]


def test_channel_unsubscribe_last_client_drops_channel():
    registry = ChannelRegistry()
    registry.subscribe("alerts", "c1")
    registry.unsubscribe("alerts", "c1")
    assert registry.channels() == {}


def test_channel_unsubscribe_missing_channel_is_noop():
    registry = ChannelRegistry()
    registry.unsubscribe("does-not-exist", "c1")
    assert registry.channels() == {}


def test_channel_unsubscribe_all_removes_from_every_channel():
    registry = ChannelRegistry()
    registry.subscribe("alerts", "c1")
    registry.subscribe("chat", "c1")
    registry.subscribe("chat", "c2")
    registry.unsubscribe_all("c1")
    assert registry.channels() == {"chat": 1}
    assert registry.subscribers("chat") == ["c2"]


def test_channel_subscribers_for_unknown_channel_is_empty():
    registry = ChannelRegistry()
    assert registry.subscribers("nope") == []


# ── Integration tests: real server + real client connections ──────
#
# No real Redis server is available in this environment, so tests use
# fakeredis as a drop-in for redis.asyncio -- it implements the same
# pub/sub and data-structure commands, and clients that share a
# fakeredis.FakeServer see each other's writes and published messages
# exactly like real clients sharing one Redis instance would.


@pytest.fixture
def redis_server():
    return fakeredis.FakeServer()


@pytest.fixture
async def running_server(tmp_path, redis_server):
    redis_client = fakeredis_aioredis.FakeRedis(server=redis_server)
    db_path = str(tmp_path / "messages.db")
    ws_server, state = create_server(
        host="127.0.0.1", port=0, redis_client=redis_client, db_path=db_path
    )
    server = await ws_server
    port = server.sockets[0].getsockname()[1]
    try:
        yield f"ws://127.0.0.1:{port}", state
    finally:
        server.close()
        await server.wait_closed()
        await state.close()
        await redis_client.aclose()


async def _make_server(tmp_path, redis_server, name):
    redis_client = fakeredis_aioredis.FakeRedis(server=redis_server)
    db_path = str(tmp_path / f"{name}.db")
    ws_server, state = create_server(
        host="127.0.0.1", port=0, redis_client=redis_client, db_path=db_path, instance_id=name
    )
    server = await ws_server
    port = server.sockets[0].getsockname()[1]
    return server, state, redis_client, f"ws://127.0.0.1:{port}"


@pytest.mark.asyncio
async def test_connect_assigns_unique_id(running_server):
    uri, state = running_server
    async with connect(uri) as ws:
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        msg = json.loads(raw)
        assert msg["type"] == "system"
        assert msg["payload"]["event"] == "connected"
        assert "client_id" in msg["payload"]
        assert state.registry.count() == 1


@pytest.mark.asyncio
async def test_two_clients_get_different_ids(running_server):
    uri, state = running_server
    async with connect(uri) as ws1, connect(uri) as ws2:
        raw1 = await asyncio.wait_for(ws1.recv(), timeout=5)
        raw2 = await asyncio.wait_for(ws2.recv(), timeout=5)
        id1 = json.loads(raw1)["payload"]["client_id"]
        id2 = json.loads(raw2)["payload"]["client_id"]
        assert id1 != id2
        assert state.registry.count() == 2


@pytest.mark.asyncio
async def test_disconnect_removes_client(running_server):
    uri, state = running_server
    ws = await connect(uri)
    await asyncio.wait_for(ws.recv(), timeout=5)
    assert state.registry.count() == 1
    await ws.close()
    await asyncio.sleep(0.2)
    assert state.registry.count() == 0


@pytest.mark.asyncio
async def test_broadcast_reaches_all_clients(running_server):
    uri, state = running_server
    async with connect(uri) as ws1, connect(uri) as ws2, connect(uri) as ws3:
        await asyncio.wait_for(ws1.recv(), timeout=5)
        await asyncio.wait_for(ws2.recv(), timeout=5)
        await asyncio.wait_for(ws3.recv(), timeout=5)

        await ws1.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "hello everyone"},
            "timestamp": "2026-08-16T00:00:00+00:00",
        }))

        for ws in (ws1, ws2, ws3):
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            assert msg["type"] == "broadcast"
            assert msg["payload"]["text"] == "hello everyone"


@pytest.mark.asyncio
async def test_broadcast_skips_disconnected_clients(running_server):
    uri, state = running_server
    ws1 = await connect(uri)
    ws2 = await connect(uri)
    await asyncio.wait_for(ws1.recv(), timeout=5)
    await asyncio.wait_for(ws2.recv(), timeout=5)

    await ws2.close()
    await asyncio.sleep(0.2)
    assert state.registry.count() == 1

    sent = await state.broadcast({"text": "still here"})
    assert sent == 1

    raw = await asyncio.wait_for(ws1.recv(), timeout=5)
    msg = json.loads(raw)
    assert msg["payload"]["text"] == "still here"
    await ws1.close()


@pytest.mark.asyncio
async def test_direct_message_reaches_only_target(running_server):
    uri, state = running_server
    async with connect(uri) as ws1, connect(uri) as ws2:
        raw1 = await asyncio.wait_for(ws1.recv(), timeout=5)
        target_id = json.loads(raw1)["payload"]["client_id"]
        await asyncio.wait_for(ws2.recv(), timeout=5)

        await ws2.send(json.dumps({
            "type": "direct",
            "payload": {"target_id": target_id, "message": {"text": "psst"}},
        }))

        raw = await asyncio.wait_for(ws1.recv(), timeout=5)
        msg = json.loads(raw)
        assert msg["type"] == "direct"
        assert msg["payload"]["text"] == "psst"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws2.recv(), timeout=0.3)


@pytest.mark.asyncio
async def test_invalid_json_gets_system_error(running_server):
    uri, state = running_server
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send("not json{{{")
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        msg = json.loads(raw)
        assert msg["type"] == "system"
        assert "error" in msg["payload"]


@pytest.mark.asyncio
async def test_unsupported_message_type_gets_system_error(running_server):
    uri, state = running_server
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({"type": "bogus", "payload": {}}))
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        msg = json.loads(raw)
        assert msg["type"] == "system"
        assert "error" in msg["payload"]


def _get_health(host_port: str) -> tuple[int, dict]:
    # http.client is blocking; the caller must run this off the event
    # loop (e.g. via asyncio.to_thread) so it doesn't stall the very
    # loop the server needs to accept the connection on.
    import http.client

    conn = http.client.HTTPConnection(host_port, timeout=5)
    try:
        conn.request("GET", "/health")
        resp = conn.getresponse()
        body = json.loads(resp.read())
        return resp.status, body
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_health_endpoint_reports_client_count(running_server):
    uri, state = running_server
    host_port = uri.removeprefix("ws://")

    status, body = await asyncio.to_thread(_get_health, host_port)
    assert status == 200
    assert body["connected_clients"] == 0

    async with connect(uri):
        await asyncio.sleep(0.1)
        status, body = await asyncio.to_thread(_get_health, host_port)
        assert status == 200
        assert body["connected_clients"] == 1


# ── Integration tests: channel subscriptions ───────────────────────

@pytest.mark.asyncio
async def test_subscribe_confirms_and_updates_registry(running_server):
    uri, state = running_server
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        msg = json.loads(raw)
        assert msg["type"] == "system"
        assert msg["payload"]["event"] == "subscribed"
        assert msg["payload"]["channel"] == "alerts"
        assert state.channels.channels() == {"alerts": 1}


@pytest.mark.asyncio
async def test_subscribe_missing_channel_gets_error(running_server):
    uri, state = running_server
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({"type": "subscribe", "payload": {}}))
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        msg = json.loads(raw)
        assert msg["type"] == "system"
        assert "error" in msg["payload"]
        assert state.channels.channels() == {}


@pytest.mark.asyncio
async def test_unsubscribe_confirms_and_updates_registry(running_server):
    uri, state = running_server
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await asyncio.wait_for(ws.recv(), timeout=5)

        await ws.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "alerts"}}))
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        msg = json.loads(raw)
        assert msg["type"] == "system"
        assert msg["payload"]["event"] == "unsubscribed"
        assert msg["payload"]["channel"] == "alerts"
        assert state.channels.channels() == {}


@pytest.mark.asyncio
async def test_client_can_subscribe_to_multiple_channels(running_server):
    uri, state = running_server
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
        await asyncio.wait_for(ws.recv(), timeout=5)

        assert state.channels.channels() == {"alerts": 1, "chat": 1}


@pytest.mark.asyncio
async def test_disconnect_removes_channel_subscriptions(running_server):
    uri, state = running_server
    ws = await connect(uri)
    await asyncio.wait_for(ws.recv(), timeout=5)
    await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await asyncio.wait_for(ws.recv(), timeout=5)
    assert state.channels.channels() == {"alerts": 1}

    await ws.close()
    await asyncio.sleep(0.2)
    assert state.channels.channels() == {}


@pytest.mark.asyncio
async def test_channel_broadcast_reaches_only_subscribers(running_server):
    uri, state = running_server
    async with connect(uri) as ws1, connect(uri) as ws2, connect(uri) as ws3:
        await asyncio.wait_for(ws1.recv(), timeout=5)
        await asyncio.wait_for(ws2.recv(), timeout=5)
        await asyncio.wait_for(ws3.recv(), timeout=5)

        # only ws1 and ws2 subscribe to "alerts"
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await asyncio.wait_for(ws1.recv(), timeout=5)
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await asyncio.wait_for(ws2.recv(), timeout=5)

        await ws3.send(json.dumps({
            "type": "broadcast",
            "payload": {"channel": "alerts", "text": "urgent"},
        }))

        for ws in (ws1, ws2):
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            assert msg["type"] == "broadcast"
            assert msg["payload"]["text"] == "urgent"
            assert msg["payload"]["channel"] == "alerts"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws3.recv(), timeout=0.3)


@pytest.mark.asyncio
async def test_broadcast_without_channel_still_reaches_everyone(running_server):
    uri, state = running_server
    async with connect(uri) as ws1, connect(uri) as ws2:
        await asyncio.wait_for(ws1.recv(), timeout=5)
        await asyncio.wait_for(ws2.recv(), timeout=5)

        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await asyncio.wait_for(ws1.recv(), timeout=5)

        await ws1.send(json.dumps({"type": "broadcast", "payload": {"text": "for everyone"}}))

        for ws in (ws1, ws2):
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            assert msg["payload"]["text"] == "for everyone"


@pytest.mark.asyncio
async def test_unsubscribed_client_does_not_receive_channel_broadcast(running_server):
    uri, state = running_server
    async with connect(uri) as ws1, connect(uri) as ws2:
        await asyncio.wait_for(ws1.recv(), timeout=5)
        await asyncio.wait_for(ws2.recv(), timeout=5)

        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await asyncio.wait_for(ws1.recv(), timeout=5)
        await ws1.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "alerts"}}))
        await asyncio.wait_for(ws1.recv(), timeout=5)

        await ws2.send(json.dumps({
            "type": "broadcast",
            "payload": {"channel": "alerts", "text": "nobody home"},
        }))

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws1.recv(), timeout=0.3)


def _get_json(host_port: str, path: str) -> tuple[int, dict]:
    import http.client

    conn = http.client.HTTPConnection(host_port, timeout=5)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        body = json.loads(resp.read())
        return resp.status, body
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_channels_endpoint_lists_active_channels(running_server):
    uri, state = running_server
    host_port = uri.removeprefix("ws://")

    async with connect(uri) as ws1, connect(uri) as ws2:
        await asyncio.wait_for(ws1.recv(), timeout=5)
        await asyncio.wait_for(ws2.recv(), timeout=5)

        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await asyncio.wait_for(ws1.recv(), timeout=5)
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await asyncio.wait_for(ws2.recv(), timeout=5)
        await ws2.send(json.dumps({"type": "subscribe", "payload": {"channel": "chat"}}))
        await asyncio.wait_for(ws2.recv(), timeout=5)

        status, body = await asyncio.to_thread(_get_json, host_port, "/channels")
        assert status == 200
        assert body["channels"] == {"alerts": 2, "chat": 1}


@pytest.mark.asyncio
async def test_channels_endpoint_empty_when_no_subscriptions(running_server):
    uri, state = running_server
    host_port = uri.removeprefix("ws://")
    status, body = await asyncio.to_thread(_get_json, host_port, "/channels")
    assert status == 200
    assert body["channels"] == {}


@pytest.mark.asyncio
async def test_channel_subscribers_endpoint_lists_ids(running_server):
    uri, state = running_server
    host_port = uri.removeprefix("ws://")

    async with connect(uri) as ws1:
        raw = await asyncio.wait_for(ws1.recv(), timeout=5)
        client_id = json.loads(raw)["payload"]["client_id"]
        await ws1.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await asyncio.wait_for(ws1.recv(), timeout=5)

        status, body = await asyncio.to_thread(_get_json, host_port, "/channels/alerts/subscribers")
        assert status == 200
        assert body["channel"] == "alerts"
        assert body["subscribers"] == [client_id]


@pytest.mark.asyncio
async def test_channel_subscribers_endpoint_empty_for_unknown_channel(running_server):
    uri, state = running_server
    host_port = uri.removeprefix("ws://")
    status, body = await asyncio.to_thread(_get_json, host_port, "/channels/nope/subscribers")
    assert status == 200
    assert body["subscribers"] == []


# ── Integration tests: Redis pub/sub as the cross-instance backbone ─

@pytest.mark.asyncio
async def test_broadcast_relays_to_client_on_another_instance(tmp_path, redis_server):
    """Two server instances share one Redis backbone (fakeredis server).
    A client on instance A broadcasts; a client connected only to instance
    B must still receive it via the Redis bus relay."""
    server_a, state_a, redis_a, uri_a = await _make_server(tmp_path, redis_server, "instance-a")
    server_b, state_b, redis_b, uri_b = await _make_server(tmp_path, redis_server, "instance-b")
    try:
        async with connect(uri_a) as ws_a, connect(uri_b) as ws_b:
            await asyncio.wait_for(ws_a.recv(), timeout=5)
            await asyncio.wait_for(ws_b.recv(), timeout=5)

            await ws_a.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": "cross-instance hello"},
            }))

            # Instance A's own client receives it via direct local delivery.
            raw_a = await asyncio.wait_for(ws_a.recv(), timeout=5)
            assert json.loads(raw_a)["payload"]["text"] == "cross-instance hello"

            # Instance B's client only receives it via the Redis bus relay,
            # since it never touched instance A's local registry.
            raw_b = await asyncio.wait_for(ws_b.recv(), timeout=5)
            msg_b = json.loads(raw_b)
            assert msg_b["type"] == "broadcast"
            assert msg_b["payload"]["text"] == "cross-instance hello"
    finally:
        for server, state, redis_client in (
            (server_a, state_a, redis_a),
            (server_b, state_b, redis_b),
        ):
            server.close()
            await server.wait_closed()
            await state.close()
            await redis_client.aclose()


@pytest.mark.asyncio
async def test_direct_message_relays_to_target_on_another_instance(tmp_path, redis_server):
    server_a, state_a, redis_a, uri_a = await _make_server(tmp_path, redis_server, "instance-a")
    server_b, state_b, redis_b, uri_b = await _make_server(tmp_path, redis_server, "instance-b")
    try:
        async with connect(uri_a) as ws_a, connect(uri_b) as ws_b:
            raw_b = await asyncio.wait_for(ws_b.recv(), timeout=5)
            target_id = json.loads(raw_b)["payload"]["client_id"]
            await asyncio.wait_for(ws_a.recv(), timeout=5)

            # ws_a's target lives on instance B, so instance A's local
            # delivery finds nothing and send_direct() returns False --
            # but the message must still reach ws_b via the bus relay.
            await ws_a.send(json.dumps({
                "type": "direct",
                "payload": {"target_id": target_id, "message": {"text": "cross-instance psst"}},
            }))

            raw = await asyncio.wait_for(ws_b.recv(), timeout=5)
            msg = json.loads(raw)
            assert msg["type"] == "direct"
            assert msg["payload"]["text"] == "cross-instance psst"

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws_a.recv(), timeout=0.3)
    finally:
        for server, state, redis_client in (
            (server_a, state_a, redis_a),
            (server_b, state_b, redis_b),
        ):
            server.close()
            await server.wait_closed()
            await state.close()
            await redis_client.aclose()


@pytest.mark.asyncio
async def test_channel_broadcast_relays_only_to_subscribed_instance(tmp_path, redis_server):
    """A channel-scoped broadcast published from instance A must only be
    delivered by instance B if instance B has a locally-subscribed client
    -- an unsubscribed client on instance B must not receive it."""
    server_a, state_a, redis_a, uri_a = await _make_server(tmp_path, redis_server, "instance-a")
    server_b, state_b, redis_b, uri_b = await _make_server(tmp_path, redis_server, "instance-b")
    try:
        async with connect(uri_a) as ws_a, connect(uri_b) as ws_b:
            await asyncio.wait_for(ws_a.recv(), timeout=5)
            await asyncio.wait_for(ws_b.recv(), timeout=5)

            await ws_b.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
            await asyncio.wait_for(ws_b.recv(), timeout=5)

            await ws_a.send(json.dumps({
                "type": "broadcast",
                "payload": {"channel": "alerts", "text": "urgent"},
            }))

            raw_b = await asyncio.wait_for(ws_b.recv(), timeout=5)
            msg_b = json.loads(raw_b)
            assert msg_b["payload"]["text"] == "urgent"

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(ws_a.recv(), timeout=0.3)
    finally:
        for server, state, redis_client in (
            (server_a, state_a, redis_a),
            (server_b, state_b, redis_b),
        ):
            server.close()
            await server.wait_closed()
            await state.close()
            await redis_client.aclose()


# ── Integration tests: connection/subscription state mirrored in Redis ─

@pytest.mark.asyncio
async def test_connect_and_disconnect_mirrored_in_redis(running_server):
    uri, state = running_server
    async with connect(uri) as ws:
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        client_id = json.loads(raw)["payload"]["client_id"]
        assert await state.redis_backbone.client_instance(client_id) == state.instance_id

    await asyncio.sleep(0.2)
    assert await state.redis_backbone.client_instance(client_id) is None


@pytest.mark.asyncio
async def test_channel_subscription_mirrored_in_redis(running_server):
    uri, state = running_server
    async with connect(uri) as ws:
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        client_id = json.loads(raw)["payload"]["client_id"]

        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await asyncio.wait_for(ws.recv(), timeout=5)
        assert await state.redis_backbone.channel_subscribers("alerts") == [client_id]
        assert await state.redis_backbone.channels() == {"alerts": 1}

        await ws.send(json.dumps({"type": "unsubscribe", "payload": {"channel": "alerts"}}))
        await asyncio.wait_for(ws.recv(), timeout=5)
        assert await state.redis_backbone.channel_subscribers("alerts") == []
        assert await state.redis_backbone.channels() == {}


@pytest.mark.asyncio
async def test_disconnect_clears_redis_channel_subscription(running_server):
    uri, state = running_server
    ws = await connect(uri)
    raw = await asyncio.wait_for(ws.recv(), timeout=5)
    client_id = json.loads(raw)["payload"]["client_id"]
    await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
    await asyncio.wait_for(ws.recv(), timeout=5)

    await ws.close()
    await asyncio.sleep(0.2)
    assert await state.redis_backbone.channel_subscribers("alerts") == []
    assert await state.redis_backbone.channels() == {}


# ── Integration tests: SQLite message persistence + GET /messages ──

@pytest.mark.asyncio
async def test_broadcast_is_persisted_and_listed_via_messages_endpoint(running_server):
    uri, state = running_server
    host_port = uri.removeprefix("ws://")
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "persist me"}}))
        await asyncio.wait_for(ws.recv(), timeout=5)

    status, body = await asyncio.to_thread(_get_json, host_port, "/messages")
    assert status == 200
    assert len(body["messages"]) == 1
    stored = body["messages"][0]
    assert stored["type"] == "broadcast"
    assert stored["channel"] is None
    assert stored["payload"]["text"] == "persist me"
    assert "timestamp" in stored


@pytest.mark.asyncio
async def test_channel_broadcast_persists_channel_name(running_server):
    uri, state = running_server
    host_port = uri.removeprefix("ws://")
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({
            "type": "broadcast",
            "payload": {"channel": "alerts", "text": "urgent"},
        }))
        await asyncio.wait_for(ws.recv(), timeout=5)

    status, body = await asyncio.to_thread(_get_json, host_port, "/messages")
    assert status == 200
    stored = [m for m in body["messages"] if m["type"] == "broadcast"][0]
    assert stored["channel"] == "alerts"


@pytest.mark.asyncio
async def test_direct_message_is_persisted(running_server):
    uri, state = running_server
    host_port = uri.removeprefix("ws://")
    async with connect(uri) as ws1, connect(uri) as ws2:
        raw1 = await asyncio.wait_for(ws1.recv(), timeout=5)
        target_id = json.loads(raw1)["payload"]["client_id"]
        await asyncio.wait_for(ws2.recv(), timeout=5)

        await ws2.send(json.dumps({
            "type": "direct",
            "payload": {"target_id": target_id, "message": {"text": "psst persisted"}},
        }))
        await asyncio.wait_for(ws1.recv(), timeout=5)

    status, body = await asyncio.to_thread(_get_json, host_port, "/messages")
    assert status == 200
    stored = body["messages"][0]
    assert stored["type"] == "direct"
    assert stored["payload"]["text"] == "psst persisted"


@pytest.mark.asyncio
async def test_messages_endpoint_pagination_newest_first(running_server):
    uri, state = running_server
    host_port = uri.removeprefix("ws://")
    async with connect(uri) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        for i in range(5):
            await ws.send(json.dumps({"type": "broadcast", "payload": {"text": f"msg-{i}"}}))
            await asyncio.wait_for(ws.recv(), timeout=5)

    status, body = await asyncio.to_thread(_get_json, host_port, "/messages?limit=2&offset=0")
    assert status == 200
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert [m["payload"]["text"] for m in body["messages"]] == ["msg-4", "msg-3"]

    status, body = await asyncio.to_thread(_get_json, host_port, "/messages?limit=2&offset=2")
    assert status == 200
    assert [m["payload"]["text"] for m in body["messages"]] == ["msg-2", "msg-1"]


@pytest.mark.asyncio
async def test_messages_endpoint_empty_when_no_messages(running_server):
    uri, state = running_server
    host_port = uri.removeprefix("ws://")
    status, body = await asyncio.to_thread(_get_json, host_port, "/messages")
    assert status == 200
    assert body["messages"] == []


@pytest.mark.asyncio
async def test_messages_persist_across_server_restart(tmp_path, redis_server):
    """The whole point of SQLite persistence (as opposed to in-memory
    history) is that message history survives a server process restart."""
    db_path = str(tmp_path / "restart.db")
    redis_client_1 = fakeredis_aioredis.FakeRedis(server=redis_server)
    ws_server_1, state_1 = create_server(
        host="127.0.0.1", port=0, redis_client=redis_client_1, db_path=db_path
    )
    server_1 = await ws_server_1
    uri_1 = f"ws://127.0.0.1:{server_1.sockets[0].getsockname()[1]}"
    async with connect(uri_1) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "before restart"}}))
        await asyncio.wait_for(ws.recv(), timeout=5)
    server_1.close()
    await server_1.wait_closed()
    await state_1.close()
    await redis_client_1.aclose()

    # A brand new server instance/process pointed at the same DATABASE_URL
    # path must see the message the previous process persisted.
    redis_client_2 = fakeredis_aioredis.FakeRedis(server=redis_server)
    ws_server_2, state_2 = create_server(
        host="127.0.0.1", port=0, redis_client=redis_client_2, db_path=db_path
    )
    server_2 = await ws_server_2
    try:
        rows = await state_2.message_store.get_messages()
        assert len(rows) == 1
        assert json.loads(rows[0]["payload"])["text"] == "before restart"
    finally:
        server_2.close()
        await server_2.wait_closed()
        await state_2.close()
        await redis_client_2.aclose()


# ── Unit tests: RedisBackbone / MessageStore ───────────────────────

@pytest.mark.asyncio
async def test_redis_backbone_publish_and_listen():
    server = fakeredis.FakeServer()
    backbone_a = RedisBackbone(fakeredis_aioredis.FakeRedis(server=server), instance_id="a")
    backbone_b = RedisBackbone(fakeredis_aioredis.FakeRedis(server=server), instance_id="b")

    events = []

    async def collect_one():
        async for envelope in backbone_b.listen():
            events.append(envelope)
            break

    task = asyncio.create_task(collect_one())
    await asyncio.sleep(0.1)
    await backbone_a.publish({"kind": "broadcast", "message": {"text": "hi"}})
    await asyncio.wait_for(task, timeout=5)

    assert events[0]["origin_instance"] == "a"
    assert events[0]["message"]["text"] == "hi"


@pytest.mark.asyncio
async def test_message_store_roundtrip(tmp_path):
    store = MessageStore(str(tmp_path / "store.db"))
    store.init_sync()
    await store.store_message("alerts", "broadcast", json.dumps({"text": "hi"}), "2026-08-16T00:00:00+00:00")
    rows = await store.get_messages()
    assert len(rows) == 1
    assert rows[0]["channel"] == "alerts"
    assert json.loads(rows[0]["payload"]) == {"text": "hi"}


def test_config_env_vars_have_sane_defaults():
    assert REDIS_URL
    assert DATABASE_URL
