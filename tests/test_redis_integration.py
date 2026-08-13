"""End-to-end tests for the Redis-mediated message backbone.

Two `NotificationServer` instances, each with its own local `ClientRegistry`
(as separate server processes would have), share a `RedisBroker` and
`RedisPresence` backed by the same `fakeredis.FakeServer` — standing in for
a real shared Redis deployment. This exercises the actual requirement: a
message accepted by one instance must reach clients connected to the other,
and direct-message routing must work even when the target is only known via
the shared presence state, not the local registry.
"""
import asyncio
import json

import fakeredis
import pytest
import websockets

from notification_server.broker import RedisBroker
from notification_server.redis_registry import RedisPresence
from notification_server.registry import ClientRegistry
from notification_server.store import MessageStore
from notification_server.ws_server import NotificationServer


@pytest.fixture
def fake_redis_server():
    return fakeredis.FakeServer()


class ServerInstance:
    def __init__(self, notification_server, ws_server, uri):
        self.notification_server = notification_server
        self.ws_server = ws_server
        self.uri = uri


async def _make_instance(fake_redis_server, store, channel="cluster"):
    redis_client = fakeredis.FakeAsyncRedis(server=fake_redis_server)
    broker = RedisBroker(redis_client, channel=channel)
    presence = RedisPresence(redis_client, server_id="server-" + str(id(redis_client)))
    server = NotificationServer(ClientRegistry(), broker=broker, presence=presence, store=store)
    await server.start()
    ws_server = await server.serve("localhost", 0)
    port = ws_server.sockets[0].getsockname()[1]
    return ServerInstance(server, ws_server, f"ws://localhost:{port}"), redis_client


async def _teardown(instance, redis_client):
    instance.ws_server.close()
    await instance.ws_server.wait_closed()
    await instance.notification_server.stop()
    await redis_client.aclose()


@pytest.fixture
async def cluster(fake_redis_server, tmp_path):
    store = MessageStore(str(tmp_path / "messages.db"))
    instance_a, redis_a = await _make_instance(fake_redis_server, store)
    instance_b, redis_b = await _make_instance(fake_redis_server, store)
    yield instance_a, instance_b, store
    await _teardown(instance_a, redis_a)
    await _teardown(instance_b, redis_b)


async def test_broadcast_reaches_clients_on_other_instance(cluster):
    instance_a, instance_b, _store = cluster
    async with websockets.connect(instance_a.uri) as ws_a, websockets.connect(
        instance_b.uri
    ) as ws_b:
        await ws_a.recv()
        await ws_b.recv()

        await ws_a.send(
            json.dumps(
                {
                    "type": "broadcast",
                    "payload": {"text": "cluster-wide"},
                    "timestamp": "2026-08-13T00:00:00Z",
                }
            )
        )

        got_a = json.loads(await asyncio.wait_for(ws_a.recv(), timeout=2))
        got_b = json.loads(await asyncio.wait_for(ws_b.recv(), timeout=2))
        assert got_a["payload"]["text"] == "cluster-wide"
        assert got_b["payload"]["text"] == "cluster-wide"


async def test_channel_broadcast_reaches_subscribers_on_other_instance(cluster):
    instance_a, instance_b, _store = cluster
    async with websockets.connect(instance_a.uri) as ws_a, websockets.connect(
        instance_b.uri
    ) as ws_b:
        await ws_a.recv()
        await ws_b.recv()

        await ws_a.send(json.dumps({"type": "subscribe", "channel": "alerts", "payload": {}}))
        await ws_a.recv()  # subscribed ack
        await ws_b.send(json.dumps({"type": "subscribe", "channel": "alerts", "payload": {}}))
        await ws_b.recv()  # subscribed ack

        await ws_a.send(
            json.dumps(
                {
                    "type": "broadcast",
                    "channel": "alerts",
                    "payload": {"text": "fire"},
                    "timestamp": "2026-08-13T00:00:00Z",
                }
            )
        )

        got_a = json.loads(await asyncio.wait_for(ws_a.recv(), timeout=2))
        got_b = json.loads(await asyncio.wait_for(ws_b.recv(), timeout=2))
        assert got_a["payload"]["text"] == "fire"
        assert got_b["payload"]["text"] == "fire"


async def test_direct_message_reaches_target_on_other_instance(cluster):
    instance_a, instance_b, _store = cluster
    async with websockets.connect(instance_a.uri) as ws_a, websockets.connect(
        instance_b.uri
    ) as ws_b:
        await ws_a.recv()
        connected_b = json.loads(await ws_b.recv())
        target_id = connected_b["payload"]["client_id"]

        await ws_a.send(
            json.dumps(
                {
                    "type": "direct",
                    "payload": {"target_id": target_id, "text": "psst"},
                    "timestamp": "2026-08-13T00:00:00Z",
                }
            )
        )

        got_b = json.loads(await asyncio.wait_for(ws_b.recv(), timeout=2))
        assert got_b["type"] == "direct"
        assert got_b["payload"]["text"] == "psst"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws_a.recv(), timeout=0.2)


async def test_direct_message_to_unknown_target_still_errors(cluster):
    instance_a, _instance_b, _store = cluster
    async with websockets.connect(instance_a.uri) as ws_a:
        await ws_a.recv()
        await ws_a.send(
            json.dumps(
                {
                    "type": "direct",
                    "payload": {"target_id": "nowhere", "text": "hi"},
                    "timestamp": "2026-08-13T00:00:00Z",
                }
            )
        )
        err = json.loads(await asyncio.wait_for(ws_a.recv(), timeout=2))
        assert err["type"] == "system"
        assert err["payload"]["event"] == "error"


async def test_messages_are_persisted_to_shared_store(cluster):
    instance_a, _instance_b, store = cluster
    async with websockets.connect(instance_a.uri) as ws_a:
        await ws_a.recv()
        await ws_a.send(json.dumps({"type": "subscribe", "channel": "alerts", "payload": {}}))
        await ws_a.recv()  # subscribed ack

        await ws_a.send(
            json.dumps(
                {
                    "type": "broadcast",
                    "channel": "alerts",
                    "payload": {"text": "persist-me"},
                    "timestamp": "2026-08-13T00:00:00Z",
                }
            )
        )
        await asyncio.wait_for(ws_a.recv(), timeout=2)

    messages = await store.alist_messages()
    assert any(m["payload"].get("text") == "persist-me" for m in messages)
    persisted = next(m for m in messages if m["payload"].get("text") == "persist-me")
    assert persisted["channel"] == "alerts"
    assert persisted["type"] == "broadcast"


async def test_disconnect_updates_shared_presence(cluster):
    instance_a, instance_b, _store = cluster
    ws_a = await websockets.connect(instance_a.uri)
    connected = json.loads(await ws_a.recv())
    client_id = connected["payload"]["client_id"]

    assert await instance_b.notification_server.presence.is_connected(client_id) is True

    await ws_a.close()
    await asyncio.sleep(0.2)

    assert await instance_b.notification_server.presence.is_connected(client_id) is False
