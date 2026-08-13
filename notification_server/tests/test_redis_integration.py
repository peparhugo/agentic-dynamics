"""Integration tests for the Redis pub/sub backbone and message persistence.

Two NotificationServer instances are wired to the same FakeRedis
FakeServer (an in-memory stand-in that behaves like a real Redis
instance shared over the network) to prove that the Redis bus, not a
direct in-process call, is what actually delivers messages -- a client
connected to one instance can be reached by a broadcast/direct message
that originated on a completely different instance.
"""

import asyncio
import json
import sqlite3
import urllib.request

import pytest
import pytest_asyncio
import websockets
from fakeredis.aioredis import FakeRedis, FakeServer

from notification_server.server import NotificationServer


def ws_uri(srv: NotificationServer) -> str:
    return f"ws://localhost:{srv.bound_port}"


async def recv_json(websocket) -> dict:
    return json.loads(await websocket.recv())


async def get_json(url: str) -> tuple[int, dict]:
    def _fetch():
        with urllib.request.urlopen(url) as resp:
            return resp.status, json.loads(resp.read())

    return await asyncio.to_thread(_fetch)


async def wait_until(predicate, timeout: float = 2.0, interval: float = 0.02) -> None:
    async def _loop():
        while not predicate():
            await asyncio.sleep(interval)

    await asyncio.wait_for(_loop(), timeout=timeout)


@pytest_asyncio.fixture
async def redis_backbone():
    """A shared fake Redis server standing in for a real broker."""
    return FakeServer()


@pytest_asyncio.fixture
async def two_instances(redis_backbone, tmp_path):
    """Two independent NotificationServer processes sharing one Redis
    backbone and one SQLite database, as CONFIG (REDIS_URL/DATABASE_URL)
    intends for a real multi-instance deployment."""
    db_path = str(tmp_path / "shared.db")
    server_a = NotificationServer(
        host="localhost",
        port=0,
        redis_client=FakeRedis(server=redis_backbone, decode_responses=True),
        db_path=db_path,
        instance_id="instance-a",
    )
    server_b = NotificationServer(
        host="localhost",
        port=0,
        redis_client=FakeRedis(server=redis_backbone, decode_responses=True),
        db_path=db_path,
        instance_id="instance-b",
    )
    await server_a.start()
    await server_b.start()
    yield server_a, server_b
    server_a.stop()
    server_b.stop()
    await server_a.wait_closed()
    await server_b.wait_closed()


# -- cross-instance broadcast via the Redis bus ------------------------------


@pytest.mark.asyncio
async def test_broadcast_from_one_instance_reaches_client_on_another(two_instances):
    server_a, server_b = two_instances
    async with websockets.connect(ws_uri(server_a)) as ws_a, websockets.connect(ws_uri(server_b)) as ws_b:
        await recv_json(ws_a)
        await recv_json(ws_b)

        await ws_a.send(json.dumps({
            "type": "broadcast",
            "payload": {"text": "hello from instance A"},
        }))

        message = await asyncio.wait_for(recv_json(ws_b), timeout=2.0)
        assert message["type"] == "broadcast"
        assert message["payload"]["text"] == "hello from instance A"


@pytest.mark.asyncio
async def test_channel_broadcast_across_instances_reaches_only_subscribers(two_instances):
    server_a, server_b = two_instances
    async with websockets.connect(ws_uri(server_a)) as ws_a, \
            websockets.connect(ws_uri(server_b)) as ws_b_subscribed, \
            websockets.connect(ws_uri(server_b)) as ws_b_unsubscribed:
        await recv_json(ws_a)
        await recv_json(ws_b_subscribed)
        await recv_json(ws_b_unsubscribed)

        await ws_b_subscribed.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws_b_subscribed)

        await ws_a.send(json.dumps({
            "type": "broadcast",
            "payload": {"channel": "alerts", "text": "fire drill"},
        }))

        message = await asyncio.wait_for(recv_json(ws_b_subscribed), timeout=2.0)
        assert message["payload"]["text"] == "fire drill"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws_b_unsubscribed.recv(), timeout=0.2)


@pytest.mark.asyncio
async def test_direct_message_across_instances(two_instances):
    server_a, server_b = two_instances
    async with websockets.connect(ws_uri(server_a)) as ws_a, websockets.connect(ws_uri(server_b)) as ws_b:
        await recv_json(ws_a)
        welcome_b = await recv_json(ws_b)
        target_id = welcome_b["payload"]["client_id"]

        await ws_a.send(json.dumps({
            "type": "direct",
            "payload": {"target_id": target_id, "text": "cross-instance ping"},
        }))

        message = await asyncio.wait_for(recv_json(ws_b), timeout=2.0)
        assert message["type"] == "direct"
        assert message["payload"]["text"] == "cross-instance ping"


@pytest.mark.asyncio
async def test_direct_message_to_target_on_unreachable_instance_is_ignored_by_sender_instance(two_instances):
    """A target that exists (known to Redis presence) but isn't locally
    connected to either running instance should not error -- the sender's
    instance can't know for certain the target has gone away since presence
    is shared, so it publishes and simply nothing delivers it locally."""
    server_a, _server_b = two_instances
    async with websockets.connect(ws_uri(server_a)) as ws_a:
        await recv_json(ws_a)
        await ws_a.send(json.dumps({
            "type": "direct",
            "payload": {"target_id": "totally-unknown-client", "text": "hi"},
        }))
        message = await recv_json(ws_a)
        assert message["type"] == "system"
        assert "error" in message["payload"]


# -- presence/channel state is shared via Redis, not local memory -----------


@pytest.mark.asyncio
async def test_channels_endpoint_reflects_subscribers_connected_to_other_instance(two_instances):
    server_a, server_b = two_instances
    async with websockets.connect(ws_uri(server_b)) as ws_b:
        await recv_json(ws_b)
        await ws_b.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws_b)

        status, body = await get_json(f"http://localhost:{server_a.bound_port}/channels")
        assert status == 200
        assert body["channels"] == {"alerts": 1}


@pytest.mark.asyncio
async def test_disconnecting_client_clears_presence_visible_from_other_instance(two_instances):
    server_a, server_b = two_instances
    async with websockets.connect(ws_uri(server_b)) as ws_b:
        await recv_json(ws_b)
        await ws_b.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws_b)

    async def _channels_empty():
        _, body = await get_json(f"http://localhost:{server_a.bound_port}/channels")
        return body["channels"] == {}

    async def _poll():
        while not await _channels_empty():
            await asyncio.sleep(0.02)

    await asyncio.wait_for(_poll(), timeout=2.0)


# -- SQLite persistence -------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcast_message_is_persisted_to_sqlite(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        await ws.send(json.dumps({"type": "subscribe", "payload": {"channel": "alerts"}}))
        await recv_json(ws)
        await ws.send(json.dumps({
            "type": "broadcast",
            "payload": {"channel": "alerts", "text": "persisted broadcast"},
        }))
        await recv_json(ws)

    status, body = await get_json(f"http://localhost:{server.bound_port}/messages")
    assert status == 200
    assert len(body["messages"]) == 1
    stored = body["messages"][0]
    assert stored["type"] == "broadcast"
    assert stored["channel"] == "alerts"
    assert stored["payload"] == {"channel": "alerts", "text": "persisted broadcast"}
    assert "timestamp" in stored


@pytest.mark.asyncio
async def test_direct_message_is_persisted_to_sqlite(server):
    async with websockets.connect(ws_uri(server)) as ws1, websockets.connect(ws_uri(server)) as ws2:
        await recv_json(ws1)
        welcome2 = await recv_json(ws2)
        target_id = welcome2["payload"]["client_id"]

        await ws1.send(json.dumps({
            "type": "direct",
            "payload": {"target_id": target_id, "text": "persisted direct"},
        }))
        await recv_json(ws2)

    status, body = await get_json(f"http://localhost:{server.bound_port}/messages")
    assert status == 200
    assert len(body["messages"]) == 1
    assert body["messages"][0]["type"] == "direct"
    assert body["messages"][0]["payload"]["text"] == "persisted direct"


@pytest.mark.asyncio
async def test_messages_endpoint_supports_limit_and_offset(server):
    async with websockets.connect(ws_uri(server)) as ws:
        await recv_json(ws)
        for i in range(5):
            await ws.send(json.dumps({
                "type": "broadcast",
                "payload": {"text": f"message {i}"},
            }))
            await recv_json(ws)

    status, body = await get_json(f"http://localhost:{server.bound_port}/messages?limit=2&offset=0")
    assert status == 200
    assert len(body["messages"]) == 2
    # newest first
    assert body["messages"][0]["payload"]["text"] == "message 4"
    assert body["messages"][1]["payload"]["text"] == "message 3"

    status, body = await get_json(f"http://localhost:{server.bound_port}/messages?limit=2&offset=2")
    assert len(body["messages"]) == 2
    assert body["messages"][0]["payload"]["text"] == "message 2"
    assert body["messages"][1]["payload"]["text"] == "message 1"


@pytest.mark.asyncio
async def test_messages_endpoint_defaults_to_limit_50_offset_0(server):
    status, body = await get_json(f"http://localhost:{server.bound_port}/messages")
    assert status == 200
    assert body["messages"] == []
    assert body["limit"] == 50
    assert body["offset"] == 0


@pytest.mark.asyncio
async def test_persisted_messages_survive_server_restart(tmp_path):
    """The messages table lives in a SQLite file, so a fresh server
    instance pointed at the same DATABASE_URL sees history from a
    previous, now-stopped, server process."""
    db_path = str(tmp_path / "restart.db")
    backbone = FakeServer()

    server1 = NotificationServer(
        host="localhost", port=0, redis_client=FakeRedis(server=backbone, decode_responses=True), db_path=db_path,
    )
    await server1.start()
    async with websockets.connect(ws_uri(server1)) as ws:
        await recv_json(ws)
        await ws.send(json.dumps({"type": "broadcast", "payload": {"text": "before restart"}}))
        await recv_json(ws)
    server1.stop()
    await server1.wait_closed()

    server2 = NotificationServer(
        host="localhost", port=0, redis_client=FakeRedis(server=backbone, decode_responses=True), db_path=db_path,
    )
    await server2.start()
    try:
        status, body = await get_json(f"http://localhost:{server2.bound_port}/messages")
        assert status == 200
        assert len(body["messages"]) == 1
        assert body["messages"][0]["payload"]["text"] == "before restart"
    finally:
        server2.stop()
        await server2.wait_closed()

    # and directly verifiable in the sqlite file itself
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT type, channel, payload FROM messages").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "broadcast"
    finally:
        conn.close()
